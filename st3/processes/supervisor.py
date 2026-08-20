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
    uuid2processes = {}  # uuid: psutil.Process(pid)
    uuid2role = {}
    uuid2heartbeat = {}
    role2uuids = {}

    uuid = None
    _lock = None
    workers_rebalance_time = None
    conn = None

    def __init__(
        self,
        sleep=30,
        heartbeat_timeout=60,
        worker_rebalance_cooldown=60,
        dev_mode=False,
    ):
        self.startup()

        while True:
            with connect(f"dbname={self.session} user=postgres") as self.conn:
                self.heartbeat()

                processes_requested, reset, shutdown = self.read_db()

                if reset:
                    self.reset()
                    continue

                if shutdown:
                    self.shutdown()
                    break

                self.clean_dead_processes(heartbeat_timeout)

                if dev_mode:
                    # TODO: file watching
                    #   - stop processes using modified files
                    #   - log event
                    raise NotImplementedError

                self.cpu_usage(processes_requested, worker_rebalance_cooldown)

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
        self.uuid = str(uuid1())
        self.workers_rebalance_time = time.now()
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
                (uuid, pid, role)
                VALUES (%s, %s, %s)
                """,
                (self.uuid, getpid(), "supervisor"),
            )

    def heartbeat(self):
        self.conn.execute(
            """UPDATE backend.processes SET heartbeat_at = now() WHERE uuid = %s""",
            (self.uuid,),
        )
        self.conn.commit()

    def read_db(self):
        processes_requested = {"messengers": 1}

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

        self.uuid2role = {}
        self.uuid2heartbeat = {}
        self.role2uuids = {}
        ret = self.conn.execute("""
            SELECT uuid, role, heartbeat_at 
            FROM backend.processes 
            WHERE stopped_at IS NULL
            """).fetchall()
        for uuid, role, heartbeat in ret:
            uuid = str(uuid)
            if uuid == self.uuid:
                continue
            if uuid not in self.uuid2processes:
                raise NotImplementedError(f"Unknown process in DB: {role=} {uuid=}")
            self.uuid2role[uuid] = role
            self.uuid2heartbeat[uuid] = heartbeat
            self.role2uuids.setdefault(role, []).append(uuid)
        if len(self.uuid2processes) != len(self.uuid2role):
            raise NotImplementedError(
                f"{list(self.uuid2processes)} != {list(self.uuid2role)}"
            )

        return processes_requested, reset, shutdown

    def reset(self):
        self.log_event("Resetting")
        draining_processes = []
        for uuid in list(self.uuid2processes):
            draining_processes.append(self.stop(uuid))
        for p in draining_processes:
            p.wait()
        self.conn.execute("NOTIFY supervisor")
        self.conn.commit()

        # start the SQL server + session DB + DB tables
        old_session = self.session.copy()
        self.start_db()
        self.workers_rebalance_time = time.now()
        new_session = self.session.copy()
        if old_session != new_session:
            # a game restart occurred (and new DB was created)
            self.register()

    def shutdown(self):
        self.log_event("Shutting down")
        draining_processes = []
        for role in ["directors", "workers", "messenger"]:
            for uuid in list(self.role2uuids[role]):
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

    def clean_dead_processes(self, heartbeat_timeout):
        draining_processes = []
        for uuid, role in self.yield_dead_processes(heartbeat_timeout):
            draining_processes.append(self.stop(uuid, role))
        for p in draining_processes:
            try:
                p.wait(timeout=5)
            except psutil.TimeoutExpired:
                p.kill()
                p.wait()

    def yield_dead_processes(self, timeout):
        for uuid in list(self.uuid2processes):
            role = self.uuid2role[uuid]
            if not self.uuid2processes[uuid].is_running():
                self.log_event(f"Crashed: {role} process with {uuid=}", "error")
                # no process left to stop
                self.conn.execute(
                    """
                    UPDATE backend.processes
                    SET stopped_at = now()
                    WHERE uuid = %s
                      AND stopped_at IS NULL
                    """,
                    (uuid,),
                )
                self.conn.commit()
                del self.uuid2processes[uuid]
                del self.uuid2role[role]
                del self.uuid2heartbeat[role]
                self.role2uuids[role].remove(uuid)
                continue
            hb = self.uuid2heartbeat[uuid]
            if (time.now() - hb).seconds >= timeout:
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
        self.uuid2processes[uuid] = p

    def stop(self, uuid: str = None, role: str = None):
        if uuid is None and role is None:
            raise ValueError("uuid or role must be specified")
        elif role is None:
            role = self.uuid2role[uuid]
        elif uuid is None:
            # kills the oldest process first
            uuid = self.role2uuids[role][0]
        self.log_event(f"Stopping {role} process with {uuid=}")
        p = self.uuid2processes.pop(uuid)
        p.terminate()
        del self.uuid2role[role]
        del self.uuid2heartbeat[role]
        self.role2uuids[role].remove(uuid)
        return p

    def cpu_usage(self, processes_requested, worker_rebalance_cooldown):
        modifier = 0
        pcts = []
        n = len(self.role2uuids["workers"])
        for uuid in self.role2uuids["workers"]:
            pct = self.uuid2processes[uuid].cpu_percent()
            self.conn.execute(
                """
                INSERT INTO backend.cpu_usage (uuid, cpu_usage) VALUES (%s, %s)
                """,
                (uuid, pct),
            )
            pcts.append(pct)
        if sum(pcts) / n >= 0.95:
            modifier += 1
        elif n > 1 and sum(pcts) / (n - 1) < 0.75:
            modifier -= 1

        # only change the number of workers after a grace period
        if (
            modifier != 0
            and (time.now() - self.workers_rebalance_time).seconds
            > worker_rebalance_cooldown
        ):
            processes_requested["workers"] += modifier
            self.workers_rebalance_time = time.now()
            self.conn.execute(
                """
                UPDATE backend.supervisor
                SET value = %s,
                    updated_at = now()
                WHERE key = %s;
                """,
                (Jsonb(processes_requested["workers"]), "workers"),
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
