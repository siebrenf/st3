import fcntl
import subprocess as sp
import sys
import time
from pathlib import Path

import psutil
from psycopg import connect

from st3 import DATA_DIR, time
from st3.db import DataBase
from st3.logging import logger


class Supervisor:
    """
    The supervisor ensures each process is healthy, and controls the number of process of each type.
    """

    processes = {}  # pid: psutil.Process(pid)
    role2pids = {}  # role: [pid,]

    def __init__(self, sleep=10, heartbeat_timeout=60, dev_mode=False):
        # max one supervisor
        self._lock = open(Path(DATA_DIR) / "supervisor.lock", "w")
        self.lock_acquire()

        # start the SQL server
        # check the game server
        # check the DB tables
        self.session = self.start_db()
        self.role2pids = self.get_role2pids()

        self.heartbeat_timeout = heartbeat_timeout

        while True:
            # query which processes should be active
            processes_requested, reset, shutdown = self.query_db()

            if reset:
                self.reset()
                continue

            if shutdown:
                self.shutdown()
                break

            for pid in self.yield_dead_processes():
                self.stop(pid)

            if dev_mode:
                # TODO: file watching
                #   - stop affected processes
                #   - log code_change event
                raise NotImplementedError

            # TODO:
            #  - measure process CPU usage (log it?)
            #  - decide if we need more/less workers

            for role, n_requested in processes_requested.items():
                n_current = len(self.role2pids[role])
                if n_current == n_requested:
                    continue
                elif n_current < n_requested:
                    self.start(role)
                else:
                    while n_current > n_requested:
                        # kills the oldest process first
                        pid = self.role2pids[role][0]
                        self.stop(pid)
                        n_current = len(self.role2pids[role])

            time.sleep(sleep)

        self.lock_release()

    def lock_acquire(self):
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

    @staticmethod
    def start_db():
        while True:
            try:
                return DataBase().session
            except RuntimeError as e:
                # game server might be between resets
                logger.warning(str(e))
                time.sleep(60)

    def query_db(self):
        with connect(f"dbname={self.session} user=postgres") as conn:
            ret = conn.execute("""SELECT * FROM processes""").fetchall()
        processes_requested = {k: v for k, v, _ in ret}
        reset = processes_requested.pop("reset")
        shutdown = processes_requested.pop("shutdown")
        return processes_requested, reset, shutdown

    def get_role2pids(self):
        role2pids = {}
        with connect(f"dbname={self.session} user=postgres") as conn:
            ret = conn.execute(
                """
                SELECT pid, role FROM processes
                ORDER BY started_at ASC
                """
            ).fetchall()
            for pid, role in ret:
                role2pids.setdefault(role, []).append(pid)
        return role2pids

    def _get_role(self, pid):
        role = "unknown_role"
        for role, pids in self.role2pids.items():
            if pid in pids:
                break
        return role

    def yield_dead_processes(self):
        hbs = self.get_heartbeats()
        for pid in self.processes.keys():
            if not psutil.pid_exists(pid):
                role = self._get_role(pid)
                self.log_event(f"Crash: {role} process with {pid=}", "error")
                yield pid
                continue
            if (time.now() - hbs[pid]).seconds >= self.heartbeat_timeout:
                role = self._get_role(pid)
                self.log_event(f"Timeout: {role} process with {pid=}", "error")
                yield pid
                continue

    def get_heartbeats(self):
        hbs = {}  # pid: last_heartbeat
        with connect(f"dbname={self.session} user=postgres") as conn:
            ret = conn.execute(
                """SELECT pid, last_heartbeat FROM processes"""
            ).fetchall()
            for pid, last_heartbeat in ret:
                hbs[pid] = last_heartbeat
        return hbs

    def start(self, role: str, *args):
        pid = sp.Popen(
            [sys.executable, "-m", f"st3.processes.{role}", *args]
        ).pid
        p = psutil.Process(pid)
        self.processes[pid] = p
        # start measuring CPU usage
        _ = p.cpu_percent()
        # register the process
        self.log_event(f"Starting {role} process with {pid=}")
        with connect(f"dbname={self.session} user=postgres") as conn:
            conn.execute(
                """
                INSERT INTO processes
                (pid, role)
                VALUES (%s, %s)
                """,
                (pid, role)
            )
        self.role2pids.setdefault(role, []).append(pid)

    def stop(self, pid: str = None):
        # TODO:
        #   - graceful shutdowns
        role = self._get_role(pid)
        self.log_event(f"Stopping {role} process with {pid=}")
        p = self.processes[pid]
        p.terminate()
        p.wait()
        self.role2pids[role].remove(pid)

    def reset(self):
        self.log_event("Resetting")
        for pid in self.processes:
            self.stop(pid)
        # start a new session DB
        self.session = self.start_db()

    def shutdown(self):
        self.log_event("Shutting down")
        for pid in self.processes:
            self.stop(pid)
        raise NotImplemented

    def log_event(self, msg, level="info"):
        with connect(f"dbname={self.session} user=postgres") as conn:
            conn.execute(
                """
                INSERT INTO events
                (msg, level)
                VALUES (%s, %s)
                """,
                (msg, level)
            )
