import fcntl
import subprocess as sp
from os import getpid
from pathlib import Path
from sys import executable
from uuid import uuid1

import psutil
from psycopg import connect
from psycopg.types.json import Jsonb

from st3 import DATA_DIR, time
from st3.db.database import DataBase
from st3.db.utils import get_session
from st3.logging import logger


class Supervisor:
    """
    The supervisor ensures each process is healthy, and controls the number of process of each type.
    """

    session = None
    processes = {}  # uuid: psutil.Process(pid)
    role2uuids = {
        "directors": [],
        "messengers": [],
        "workers": [],
    }
    uuid2role = {}  # uuid: role

    uuid = None
    pid = None
    _lock = None
    start_time = None  # updated on reset
    conn = None

    def __init__(self, sleep=30, heartbeat_timeout=60, dev_mode=False):
        self.startup()

        while True:
            with connect(f"dbname={self.session} user=postgres") as self.conn:
                self.heartbeat()

                processes_requested, heartbeats, reset, shutdown = self.read_db()

                if reset:
                    self.reset()
                    continue

                if shutdown:
                    self.shutdown()
                    break

                self.clean_dead_processes(heartbeats, heartbeat_timeout)

                if dev_mode:
                    # TODO: file watching
                    #   - stop processes using modified files
                    #   - log event
                    raise NotImplementedError

                self.cpu_usage(processes_requested)

                self.balance_processes(processes_requested)

            time.sleep(sleep)

    def startup(self):
        # max one supervisor
        self.lock_acquire()

        # start the SQL server + session DB + DB tables
        self.start_db()

        # kill orphaned processes & mark them as stopped
        self.clean_old_processes()

        # register supervisor process
        self.pid = getpid()
        self.uuid = str(uuid1())
        self.start_time = time.now()
        self.register()

    def clean_old_processes(self):
        with connect(f"dbname={self.session} user=postgres") as conn:
            ret = conn.execute(
                """SELECT uuid, pid FROM backend.processes WHERE stopped_at IS NULL"""
            ).fetchall()
            for uuid, pid in ret:
                uuid = str(uuid)
                # check if the PID and UUID both exist
                if psutil.pid_exists(pid):
                    p = psutil.Process(pid)
                    if uuid in p.cmdline():
                        # orphaned process from a previous supervisor
                        try:
                            p.wait(timeout=5)
                        except psutil.TimeoutExpired:
                            p.kill()
                            p.wait()
                # mark process as stopped
                conn.execute(
                    """
                    UPDATE backend.processes
                    SET stopped_at = now()
                    WHERE uuid = %s
                    """,
                    (uuid,),
                )

    def register(self):
        with connect(f"dbname={self.session} user=postgres") as conn:
            conn.execute(
                """
                INSERT INTO backend.processes
                (uuid, pid, role, started_at)
                VALUES (%s, %s, %s, %s)
                """,
                (self.uuid, self.pid, "supervisor", self.start_time),
            )

    def shutdown(self):
        self.log_event("Shutting down")
        draining_processes = []
        for role in ["directors", "workers", "messenger"]:
            for uuid in self.role2uuids[role]:
                draining_processes.append(self.stop(uuid))
        for p in draining_processes:
            p.wait()
        self.conn.execute(
            """
            UPDATE backend.processes
            SET stopped_at = now()
            WHERE uuid = %s
            """,
            (self.uuid,),
        )
        self.conn.execute("NOTIFY supervisor")
        self.conn.commit()
        self.lock_release()

    def reset(self):
        self.log_event("Resetting")
        draining_processes = []
        for uuid in self.processes:
            draining_processes.append(self.stop(uuid))
        for p in draining_processes:
            p.wait()
        self.conn.execute("NOTIFY supervisor")
        self.conn.commit()

        # start the SQL server + session DB + DB tables
        old_session = self.session.copy()
        self.start_db()
        self.start_time = time.now()
        new_session = self.session.copy()
        if old_session != new_session:
            # a game restart occurred (and new DB was created)
            self.register()

    def lock_acquire(self):
        self._lock = open(Path(DATA_DIR) / "supervisor.lock", "w")
        try:
            fcntl.flock(
                self._lock,
                fcntl.LOCK_EX | fcntl.LOCK_NB,
            )
        except BlockingIOError:
            self._lock.close()
            self._lock = None
            raise RuntimeError("Supervisor already running")

    def lock_release(self):
        if self._lock is not None:
            fcntl.flock(self._lock, fcntl.LOCK_UN)
            self._lock.close()
            self._lock = None

    def start_db(self):
        while True:
            try:
                self.session = DataBase().session
            except RuntimeError as e:
                # game server might be between resets
                logger.warning(str(e))
                time.sleep(60)

    def heartbeat(self):
        self.conn.execute(
            """UPDATE backend.processes SET heartbeat_at = now() WHERE uuid = %s""",
            (self.uuid,),
        )
        self.conn.commit()

    def read_db(self):
        processes_requested = {
            "messengers": 1,
        }

        n = len(
            self.conn.execute(
                """SELECT symbol FROM game.agents WHERE role = %s""", ("player",)
            ).fetchall()
        )
        processes_requested["directors"] = n

        reset = False
        shutdown = False
        ret = self.conn.execute(
            """SELECT key, value FROM backend.supervisor"""
        ).fetchall()
        for k, v in ret:
            if k == "workers":
                processes_requested["workers"] = v
            elif k == "reset":
                reset = v
            elif k == "shutdown":
                shutdown = v
            else:
                raise ValueError(f"{k}: {v}")

        heartbeats = {}
        ret = self.conn.execute(
            """
            SELECT uuid, heartbeat_at FROM backend.processes WHERE stopped_at IS NULL
            """,
            (None,),
        ).fetchall()
        for uuid, heartbeat in ret:
            heartbeats[uuid] = heartbeat

        return processes_requested, heartbeats, reset, shutdown

    def update_roles_and_uuids(self):
        ret = self.conn.execute(
            """
            SELECT uid, role FROM backend.processes
            WHERE stopped_at IS NULL
            ORDER BY started_at ASC
            """
        ).fetchall()
        for uuid, role in ret:
            if uuid not in self.role2uuids[role]:
                self.role2uuids[role].append(uuid)

        for role, uuids in self.role2uuids.items():
            for uuid in uuids:
                self.uuid2role[uuid] = role

    def clean_dead_processes(self, heartbeats, heartbeat_timeout):
        draining_processes = []
        for uuid, role in self.yield_dead_processes(heartbeats, heartbeat_timeout):
            draining_processes.append(self.stop(uuid, role))
        for p in draining_processes:
            try:
                p.wait(timeout=5)
            except psutil.TimeoutExpired:
                p.kill()
                p.wait()

    def yield_dead_processes(self, hbs, timeout):
        # TODO: use PIDs from DB instead of local dict?
        for uuid in list(self.processes):
            # if not psutil.pid_exists(pid):
            #     self.log_event(f"Crashed: {role} process with {uuid=}", "error")
            #     # no process left to stop
            #     self.conn.execute(
            #         """
            #         UPDATE backend.processes
            #         SET stopped_at = now()
            #         WHERE uuid = %s
            #           AND stopped_at IS NULL
            #         """,
            #         (uuid,),
            #     )
            #     self.conn.commit()
            #     del self.processes[uuid]
            #     self.role2uuids[role].remove(uuid)
            #     del self.uuid2role[uuid]
            #     continue
            if (time.now() - hbs[uuid]).seconds >= timeout:
                role = self.uuid2role[uuid]
                self.log_event(f"Timeout: {role} process with {uuid=}", "error")
                yield uuid, role
                continue

    def start(self, role: str):
        uuid = str(uuid1())
        pid = sp.Popen([executable, "-m", f"st3.processes.{role}", uuid]).pid
        self.log_event(f"Starting {role} process with {uuid=}")
        p = psutil.Process(pid)
        # start measuring CPU usage
        _ = p.cpu_percent()
        self.processes[uuid] = p
        self.role2uuids[role].append(uuid)
        self.uuid2role[uuid] = role

    def stop(self, uuid: str = None, role: str = None):
        if uuid is None and role is None:
            raise ValueError("uuid or role must be specified")
        elif role is None:
            role = self.uuid2role[uuid]
        elif uuid is None:
            # kills the oldest process first
            uuid = self.role2uuids[role][0]
        self.log_event(f"Stopping {role} process with {uuid=}")
        p = self.processes[uuid]
        p.terminate()
        del self.processes[uuid]
        self.role2uuids[role].remove(uuid)
        del self.uuid2role[uuid]
        return p

    def cpu_usage(self, processes_requested):
        modifier = 0
        pcts = []
        n = len(self.role2uuids["workers"])
        for uuid in self.role2uuids["workers"]:
            p = self.processes[uuid]
            pcts.append(p.cpu_percent())
        if sum(pcts) / n > 0.9:
            modifier += 1
        elif n > 1 and sum(pcts) / (n - 1) < 0.6:
            modifier -= 1

        # only change the number of workers after a grace period
        if modifier != 0 and (time.now() - self.start_time).seconds > 300:
            processes_requested["workers"] += modifier
            self.conn.execute(
                """
                UPDATE backend.supervisor
                SET value = %s,
                    updated_at = now()
                WHERE key = %s;
                """,
                (Jsonb(processes_requested["workers"]), "workers"),
            )
        for i, uuid in enumerate(self.role2uuids["workers"]):
            self.conn.execute(
                """
                INSERT INTO backend.cpu_usage (uuid, cpu_usage)
                """,
                (uuid, pcts[i]),
            )
        self.conn.commit()

    def balance_processes(self, processes_requested):
        for role, n_requested in processes_requested.items():
            n_current = len(self.role2uuids[role])

            while n_current < n_requested:
                self.start(role)
                n_current += 1

            draining_processes = []
            while n_current > n_requested:
                draining_processes.append(self.stop(role=role))
                n_current -= 1
            for p in draining_processes:
                p.wait()

    def log_event(self, msg, level="info"):
        self.conn.execute(
            """
            INSERT INTO backend.events
            (msg, level)
            VALUES (%s, %s)
            """,
            (msg, level),
        )
        self.conn.commit()


def reset_supervisor():
    session = get_session()
    with connect(f"dbname={session} user=postgres") as conn:
        conn.execute("LISTEN supervisor")
        conn.execute("""UPDATE backend.supervisor SET reset = to_jsonb(true)""")
        conn.commit()
        for _ in conn.notifies():
            break


def shutdown_supervisor():
    session = get_session()
    with connect(f"dbname={session} user=postgres") as conn:
        conn.execute("LISTEN supervisor")
        conn.execute("""UPDATE backend.supervisor SET shutdown = to_jsonb(true)""")
        conn.commit()
        for _ in conn.notifies():
            break
