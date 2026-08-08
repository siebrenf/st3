"""
This script handles the backend and automation portion of the game.
"""
import os
import time
import subprocess as sp
import requests

# from dotenv import load_dotenv
from xdg import XDG_DATA_HOME


class DataBase:

    def __init__(self, session: str = None, user: str = "postgres"):
        data_dir = os.path.join(XDG_DATA_HOME, "st3")
        self.path = os.path.join(data_dir, "sql")
        self.log = os.path.join(data_dir, "sql_log.txt")

        if session is None:
            status = requests.get("https://api.spacetraders.io/v2/").json()
            last_reset = status["resetDate"]
            next_reset = status["serverResets"]["next"]
            session = f"{last_reset}_{next_reset[:10]}"
        self.session = session
        self.user = user

        if not self.exists():
            self.create()
        if not self.status():
            self.start()

    def start(self):
        sp.run(f"pg_ctl -D {self.path} -l {self.log} start", shell=True, check=True, capture_output=True)
        
    def stop(self):
        sp.run(f"pg_ctl -D {self.path} stop", shell=True, check=True, capture_output=True)

    def status(self):
        """check if the SQL server is running"""
        if not os.path.exists(self.path):
            raise FileNotFoundError

        # check=False because an offline server returns exit code 3
        ret = sp.run(f"pg_ctl -D {self.path} status", shell=True, check=False, capture_output=True)
        if ret.returncode == 0:
            running = True
        elif ret.returncode == 3:
            running = False
        else:
            code = ret.returncode
            out = ret.stdout.decode().strip()
            err = ret.stderr.decode().strip()
            raise NotImplementedError(f"Error code: {code}, stdout: {out}, stderr: {err}")
        return running

    def exists(self):
        try:
            self.status()
        except FileNotFoundError:
            return False
        except NotImplementedError as e:
            if "not a database cluster directory" in str(e):
                return False
            else:
                raise e
        return True

    def create(self):
        """create the database"""
        if os.path.exists(self.path):
            raise FileExistsError(f"A DB already exists at {self.path}")

        db_dir = os.path.dirname(self.path)
        if not os.path.exists(db_dir):
            os.makedirs(db_dir)

        sp.run(
            f"initdb --username={self.user} {self.path}",
            shell=True,
            check=True,
            capture_output=True,
        )
        # start the server in order to create the database
        self.start()
        sp.run(
            f"createdb --no-password --owner={self.user} --user={self.user} {self.session}",
            shell=True,
            check=True,
            capture_output=True,
        )
        # self.stop()


class Supervisor:
    workers = {}
    terminate = False

    def __init__(self, dev_mode=False):
        # sanity checks
        #   - other supervisor(s) running?
        #   - >1 DBs running?
        #   - game server running?
        pass

        # start the DB
        pass

        # initialize missing DB tables
        pass

        while True:

            # query which processes should be active
            #   - list processes expected
            #   - on shutdown request:
            #     - self.terminate = True
            pass

            if self.terminate:
                # update DB:
                #   - shutdown completed (remove shutdown request)
                #   - log shutdown event
                pass

                break

            # query which processes are active
            #   - query last heartbeat
            #   - on timeout:
            #     - update table worker_status
            #   - on crash:
            #     - list processes to restart
            #     - log crash events
            #     - update table worker_status
            #   - on missing:
            #     - list processes to start
            pass

            if dev_mode:
                # file watching
                #   - list processes to restart
                #   - log code_change event
                pass

            # resolve (re)start and stop commands
            #   - on requested deactivations:
            #     - log stop event
            pass

            # stop processes
            #   - ensure graceful shutdowns
            pass

            # start processes
            #   - log start event
            pass

            time.sleep(1)

        # # stop the DB
        # pass



if __name__ == "__main__":
    s = Supervisor(True)
