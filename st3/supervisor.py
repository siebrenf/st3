"""
This script handles the backend and automation portion of the game.
"""

import fcntl
import time
from pathlib import Path

from psycopg import connect

from st3 import data_dir
from st3.db import DataBase
from st3.logging import logger


class Supervisor:
    workers = {}

    def __init__(self, sleep=1, dev_mode=False):
        # max one supervisor
        self._lock = open(Path(data_dir) / "supervisor.lock", "w")
        self.lock_acquire()

        # start the SQL server
        # check the game server
        # check the DB tables
        self.session = self.start_db()

        while True:
            # query which processes should be active
            workers_requested, reset, shutdown = self.query_db()

            if reset:
                # TODO:
                #   - log reset event
                #   - stop the director
                #   - stop the workers
                #   - stop the messenger
                for role, pid in self.workers.items():
                    self.stop(role, pid)
                # start a new session DB
                self.session = self.start_db()
                continue

            if shutdown:
                self.shutdown()
                break

            # query which processes are active
            workers_alive, workers_dead = self.pulse_workers()

            if dev_mode:
                # file watching
                #   - add worker to workers_dead
                #   - log code_change event
                pass

            # resolve (re)start and stop commands
            for role, pid in workers_dead.items():
                self.stop(role, pid)

            for role, n_workers in workers_requested.items():
                n = n_workers - workers_alive.get(role, 0)
                if n > 0:
                    self.start(role)
                elif n < 0:
                    self.stop(role)

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
                break
            except RuntimeError as e:
                # game server might be between resets
                logger.warning(str(e))
                time.sleep(60)

    def query_db(self):
        with connect(f"dbname={self.session} user=postgres") as conn:
            ret = conn.execute("""SELECT * FROM workers""").fetchall()
        workers_requested = {k: v for k, v, _ in ret}
        reset = workers_requested.pop("reset")
        shutdown = workers_requested.pop("shutdown")
        return workers_requested, reset, shutdown

    def pulse_workers(self):
        workers_alive = {}
        workers_dead = {}
        # TODO:
        #   - query last heartbeat
        #   - on timeout:
        #     - update table worker_status in DB
        #     - log timeout events
        #   - on crash:
        #     - update table worker_status in DB
        #     - log crash events
        #     - list processes to restart
        #   - on missing:
        #     - list processes to start
        raise NotImplemented

    def start(self, role: str):
        # TODO:
        #   - log start event
        raise NotImplemented

    def stop(self, role: str, pid=None):
        # TODO:
        #   - accept pid to specify a worker
        #   - ensure graceful shutdowns
        #   - log stop event
        raise NotImplemented

    def shutdown(self):
        # TODO:
        #  - graceful shutdowns for all workers
        #  - remove shutdown command from DB
        #  - log shutdown event
        raise NotImplemented
