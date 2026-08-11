from psycopg import connect
from psycopg.rows import dict_row

from st3 import time
from st3.db.utils import get_session
from st3.request import Request


class Messenger:
    def __init__(self):
        self.session, next_reset = get_session(True)
        self.next_reset = time.read(next_reset)
        self.request = Request()
        self.conn = connect(
            f"dbname={self.session} user=postgres", row_factory=dict_row
        )

        self.conn.execute("LISTEN api_queue")
        self.conn.commit()

        while True:
            api_request = self.conn.execute(
                """
                SELECT
                    r.*,
                    a.token
                FROM api_requests AS r
                LEFT JOIN agents AS a ON a.symbol = r.agent
                WHERE r.completed = false
                ORDER BY r.priority DESC, r.id ASC
                LIMIT 1;
                """
            ).fetchone()
            if api_request is None:
                # sleep until notified or until timeout
                for _ in self.conn.notifies(timeout=10):
                    break
                continue

            self.conn.commit()

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
                UPDATE api_requests
                SET completed = true,
                 completed_at = now(),
                 response_status = %s,
                 response_headers = %s,
                 response_json = %s
                WHERE id = %s
                """,
                (ret.status_code, ret.headers, ret.json(), api_request["id"]),
            )
            self.conn.execute(
                "SELECT pg_notify('api_queue', %s)",
                (api_request["id"],),
            )
            self.conn.commit()

    def server_reset(self, api_request, response):
        """
        The server has reset if
          - the response is invalid,
          - the token is invalid, and
          - the agent is present in the DB
        """
        # check for valid responses
        if response.status_code in [200, 201]:
            return False

        # check if the session has expired
        if time.remaining(self.next_reset) > 0:
            return False

        # check for invalid token error (TODO: check code)
        if response.json().get("error", {}).get("code") != 4104:
            return False

        # check if the token should be valid
        if self.conn.execute(
            """
            SELECT * FROM agents
            WHERE symbol = %s
            """,
            (api_request["agent"],),
        ).fetchone():
            return False

        # TODO: log response?
        self.conn.execute(
            """
            UPDATE workers
            SET values = to_jsonb(false)
            WHERE key = %s
            """,
            ("reset",),
        )
        self.conn.commit()
        self.conn.close()
        return True
