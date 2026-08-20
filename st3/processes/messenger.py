import signal
from os import getpid
from sys import argv

from psycopg import connect
from psycopg.rows import dict_row

from st3 import time
from st3.db.utils import get_session
from st3.request import Request


class Messenger:
    def __init__(self, uuid):
        self.uuid = uuid
        self.session, self.next_reset = get_session(True)
        self.request = Request()
        self.conn = connect(
            f"dbname={self.session} user=postgres", row_factory=dict_row
        )
        self.register()

        # graceful shutdown
        self.running = True
        signal.signal(signal.SIGTERM, self.shutdown)
        while self.running:
            self.heartbeat()

            api_request = self.conn.execute("""
                SELECT
                    r.*,
                    a.token
                FROM backend.api_requests AS r
                LEFT JOIN game.agents AS a ON a.symbol = r.agent
                WHERE r.completed = false
                ORDER BY r.priority DESC, r.id ASC
                LIMIT 1;
                """).fetchone()
            if api_request is None:
                # sleep until notified or timeout
                for _ in self.conn.notifies(timeout=10):
                    break
                continue

            ret = self.request(
                method=api_request["method"],
                endpoint=api_request["endpoint"],
                token=api_request["token"],
                json=api_request["json"],
                params=api_request["params"],
            )

            if self.server_reset(api_request, ret):
                break

            self.conn.execute(
                """
                UPDATE backend.api_requests
                SET 
                    completed = true,
                    completed_at = now(),
                    response_status = %s,
                    response_headers = %s,
                    response_json = %s
                WHERE id = %s
                """,
                (ret.status_code, ret.headers, ret.json(), api_request["id"]),
            )
            self.conn.execute(
                "SELECT pg_notify('api_response', %s)",
                (str(api_request["id"]),),
            )
            self.conn.commit()

        self.deregister()
        self.conn.close()

    def register(self):
        self.conn.execute(
            """
            INSERT INTO backend.processes
            (uuid, pid, role)
            VALUES (%s, %s, %s)
            """,
            (self.uuid, getpid(), "messenger"),
        )
        self.conn.execute("LISTEN api_queue")
        self.conn.commit()

    def deregister(self):
        self.conn.execute(
            """
            UPDATE backend.processes
            SET stopped_at = now()
            WHERE uuid = %s
            """,
            (self.uuid,),
        )
        self.conn.commit()

    def shutdown(self, signum, frame):
        self.running = False

    def heartbeat(self):
        self.conn.execute(
            """UPDATE backend.processes SET heartbeat_at = now() WHERE uuid = %s""",
            (self.uuid,),
        )
        self.conn.commit()

    def server_reset(self, api_request, response):
        """
        The server has reset if
          - the response is invalid,
          - the session has expired,
          - the token is invalid, and
          - the agent is present in the DB
        """
        # check for valid responses
        if response.status_code in [200, 201]:
            return False

        # check if the session has expired
        if time.remaining(self.next_reset) > 0:
            return False

        # check for invalid token error
        # TODO: check for status_code == 401?
        if response.json().get("error", {}).get("code") != 4104:
            return False

        # check if the token should be valid
        if self.conn.execute(
            """
            SELECT * FROM game.agents
            WHERE symbol = %s
            """,
            (api_request["agent"],),
        ).fetchone():
            return False

        self.conn.execute(
            """
            UPDATE backend.supervisor
            SET values = to_jsonb(true)
            WHERE key = %s
            """,
            ("reset",),
        )
        self.conn.commit()
        return True


if __name__ == "__main__":
    m = Messenger(uuid=argv[1])
