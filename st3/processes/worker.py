import signal
from os import getpid
from sys import argv

from psycopg import connect
from psycopg.rows import dict_row

from st3 import time
from st3.db.utils import get_session
from st3.request import Request

# class RequestDB:
#     def __init__(self, session):
#         self.session = session
#         self.conn = None
#
#     def _open(self):
#         self.conn = connect(f"dbname={self.session} user=postgres")
#
#     def _close(self):
#         self.conn.close()
#         self.conn = None
#
#     def __enter__(self):
#         if self.conn is None:
#             self._open()
#         return self
#
#     def __exit__(self, exc_type, exc_value, traceback):
#         if self.conn is not None:
#             self._close()
#
#     def get(self, endpoint, json=None, params=None, agent=None, priority=0):
#         return self._queue_request("get", endpoint, json, params, agent, priority)
#
#     def post(self, endpoint, json=None, agent=None, priority=0):
#         return self._queue_request("post", endpoint, json, None, agent, priority)
#
#     def patch(self, endpoint, json=None, agent=None, priority=0):
#         return self._queue_request("patch", endpoint, json, None, agent, priority)
#
#     def get_all(self, endpoint, json=None, agent=None, priority=0):
#         """yield all results from the get request, not just the first 20 results."""
#         close = False
#         if self.conn is None:
#             self._open()
#             close = True
#
#         total = 0
#         page = 0
#         while True:
#             page += 1
#             resp_json = self.get(
#                 endpoint,
#                 json,
#                 {"page": page, "limit": 20},
#                 agent,
#                 priority,
#             )[0]
#             yield resp_json
#             total += len(resp_json["data"])
#             if total == resp_json["meta"]["total"]:
#                 break
#
#         if close:
#             self._close()
#         return
#
#     def _queue_request(self, method, endpoint, json, params, agent, priority):
#         close = False
#         if self.conn is None:
#             self._open()
#             close = True
#
#         self.conn.execute("LISTEN api_response")
#         request_id = self.conn.execute(
#             """
#             INSERT INTO api_requests
#                 (agent, method, endpoint, json, params, priority)
#             VALUES (%s, %s, %s, %s, %s, %s)
#             RETURNING id
#             """,
#             (agent, method, endpoint, json, params, priority),
#         ).fetchone()[0]
#         self.conn.execute("NOTIFY api_queue")
#         self.conn.commit()
#
#         while True:
#             for notify in self.conn.notifies(timeout=30, stop_after=1):
#                 if notify.payload == str(request_id):
#                     break
#
#             response_json, response_status, completed = self.conn.execute(
#                 """
#                 SELECT response_json, response_status, completed
#                 FROM api_requests
#                 WHERE id = %s
#                 """,
#                 (request_id,),
#             ).fetchone()
#
#             if completed:
#                 break
#
#         if close:
#             self._close()
#         return response_json, response_status


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

            work = self.available_work()  # TODO
            if work is None:
                # sleep until notified
                for _ in self.conn.notifies(timeout=None, stop_after=1):
                    continue

            # TODO: use work
            pass

            # - listen (with timeout)
            # - option 1:
            #     - read available plan
            #     - CPU heavy: convert plan into route with steps
            #       (navigate, refuel, repair, buy cargo, sell cargo, jettison cargo, supply, deliver, market, shipyard)
            #     - write route to routes + heartbeat
            # - option 2:
            #     - read available steps of currently ready task
            #     - write api requests to queue + heartbeat
            # - option 3:
            #     - read available steps of currently ready task
            #     - parse API response
            #     - write response to game state + update route + heartbeat
            #     - continue with option 2 if possible
            # - option 4:
            #     - read available steps of currently ready task
            #     - CPU heavy: review options
            #     - update route + heartbeat
            #     - continue with option 2 if possible

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
        self.conn.execute("LISTEN work_available")  # TODO
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

    def available_work(self):
        return self.conn.execute(
            """
            SELECT *
            FROM (
                SELECT
                    id,
                    'api_request' AS work_type,
                    1 AS priority
                FROM backend.api_requests
                WHERE requested_at IS NOT NULL
                  AND completed_at IS NULL
                ORDER BY priority DESC, id ASC
                LIMIT 1

                UNION ALL

                SELECT
                    id,
                    'table2' AS work_type,
                    2 AS priority
                FROM table2
                WHERE processed = false

                UNION ALL

                SELECT
                    id,
                    'table3' AS work_type,
                    3 AS priority
                FROM table3
                WHERE processed = false
            ) AS work
            ORDER BY priority
            LIMIT 1
            """
        ).fetchone()


if __name__ == "__main__":
    m = Worker(uuid=argv[1])
