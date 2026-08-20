import signal
from os import getpid
from sys import argv

from psycopg import connect
from psycopg.rows import dict_row

from st3 import time
from st3.db.utils import get_session
from st3.request import Request


class RequestDB:
    def __init__(self):
        self.session = get_session()
        self.conn = None

    def _open(self):
        self.conn = connect(f"dbname={self.session} user=postgres")

    def _close(self):
        self.conn.close()
        self.conn = None

    def __enter__(self):
        if self.conn is None:
            self._open()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.conn is not None:
            self._close()

    def get(self, endpoint, json=None, params=None, agent=None, priority=0):
        return self._queue_request("get", endpoint, json, params, agent, priority)

    def post(self, endpoint, json=None, agent=None, priority=0):
        return self._queue_request("post", endpoint, json, None, agent, priority)

    def patch(self, endpoint, json=None, agent=None, priority=0):
        return self._queue_request("patch", endpoint, json, None, agent, priority)

    def get_all(self, endpoint, json=None, agent=None, priority=0):
        """yield all results from the get request, not just the first 20 results."""
        close = False
        if self.conn is None:
            self._open()
            close = True

        total = 0
        page = 0
        while True:
            page += 1
            resp_json = self.get(
                endpoint,
                json,
                {"page": page, "limit": 20},
                agent,
                priority,
            )[0]
            yield resp_json
            total += len(resp_json["data"])
            if total == resp_json["meta"]["total"]:
                break

        if close:
            self._close()
        return

    def _queue_request(self, method, endpoint, json, params, agent, priority):
        close = False
        if self.conn is None:
            self._open()
            close = True

        self.conn.execute("LISTEN api_response")
        request_id = self.conn.execute(
            """
            INSERT INTO api_requests 
                (agent, method, endpoint, json, params, priority)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (agent, method, endpoint, json, params, priority),
        ).fetchone()[0]
        self.conn.execute("NOTIFY api_queue")
        self.conn.commit()

        while True:
            for notify in self.conn.notifies(timeout=30):
                if notify.payload == str(request_id):
                    break

            response_json, response_status, completed = self.conn.execute(
                """
                SELECT response_json, response_status, completed
                FROM api_requests 
                WHERE id = %s
                """,
                (request_id,),
            ).fetchone()

            if completed:
                break

        if close:
            self._close()
        return response_json, response_status


class Worker:
    def __init__(self, uuid):
        self.uuid = uuid
        self.session = get_session()
        # self.request = Request()
        self.conn = connect(
            f"dbname={self.session} user=postgres", row_factory=dict_row
        )
        self.register()

        # graceful shutdown
        self.running = True
        signal.signal(signal.SIGTERM, self.shutdown)
        while self.running:
            self.heartbeat()

            # api_request = self.conn.execute("""
            #     SELECT
            #         r.*,
            #         a.token
            #     FROM backend.api_requests AS r
            #     LEFT JOIN game.agents AS a ON a.symbol = r.agent
            #     WHERE r.completed = false
            #     ORDER BY r.priority DESC, r.id ASC
            #     LIMIT 1;
            #     """).fetchone()
            # if api_request is None:
            #     # sleep until notified or timeout
            #     for _ in self.conn.notifies(timeout=10):
            #         break
            #     continue
            #
            # ret = self.request(
            #     method=api_request["method"],
            #     endpoint=api_request["endpoint"],
            #     token=api_request["token"],
            #     json=api_request["json"],
            #     params=api_request["params"],
            # )
            #
            # if self.server_reset(api_request, ret):
            #     break
            #
            # self.conn.execute(
            #     """
            #     UPDATE backend.api_requests
            #     SET
            #         completed = true,
            #         completed_at = now(),
            #         response_status = %s,
            #         response_headers = %s,
            #         response_json = %s
            #     WHERE id = %s
            #     """,
            #     (ret.status_code, ret.headers, ret.json(), api_request["id"]),
            # )
            # self.conn.execute(
            #     "SELECT pg_notify('api_response', %s)",
            #     (str(api_request["id"]),),
            # )
            #
            # self.conn.commit()

        self.deregister()
        self.conn.close()

    def register(self):
        self.conn.execute(
            """
            INSERT INTO backend.processes
            (uuid, pid, role)
            VALUES (%s, %s, %s)
            """,
            (self.uuid, getpid(), "worker"),
        )
        # self.conn.execute("LISTEN api_queue")  TODO: where to listen to?
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


if __name__ == "__main__":
    m = Worker(uuid=argv[1])
