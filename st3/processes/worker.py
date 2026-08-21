import signal
from os import getpid
from sys import argv

from psycopg import connect
from psycopg.rows import dict_row

from st3 import time
from st3.db.utils import get_session

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
        self.heartbeat_cooldown = 10
        self.heartbeat_at = time.now()
        self.conn = connect(
            f"dbname={self.session} user=postgres", row_factory=dict_row
        )
        self.register()

        # graceful shutdown
        self.running = True
        signal.signal(signal.SIGTERM, self.shutdown)
        while self.running:
            sleep = True

            self.heartbeat()

            # process an API response
            api_response = self.get_api_response()
            if api_response is not None:
                # update game state
                self.update_game(api_response)
                # mark request as completed
                self.update_api_requests(api_response)
                # mark action as completed
                plan_id, cooldown = self.update_action(api_response=api_response)
                # mark plan progress
                goal_id = self.update_plan(plan_id, cooldown)
                # mark goal ready for review
                self.update_goal(goal_id)
                self.conn.commit()
                sleep = False

            # process an action
            action = self.get_action()
            if action is not None:
                # 1 action = 1 API request
                self.queue_api_requests(action)
                # mark action progress
                self.update_action(action=action)
                self.conn.commit()
                sleep = False

            # process a goal
            goal = self.get_goal()
            if goal is not None:
                # 1 goal >= 0 subgoals
                subgoals = self.formulate_subgoals(goal)
                if subgoals:
                    for subgoal in subgoals:
                        self.queue_goal(subgoal)
                    # mark goal progress
                    self.update_goal(goal, subgoals=subgoals)

                # 1 goal >= 0 plans
                plans = self.formulate_plans(goal)
                if plans:
                    for plan in plans:
                        self.queue_plan(plan)
                        # 1 plan >= 1 actions
                        self.queue_actions(plan)
                        # mark goal progress
                        self.update_goal(goal, plans=plans)

                self.conn.commit()
                sleep = False

            if sleep:
                # sleep until notified or timeout
                for _ in self.conn.notifies(timeout=10):
                    continue

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
        self.conn.execute("LISTEN work")
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
        t = time.now()
        if t > self.heartbeat_at + self.heartbeat_cooldown:
            self.conn.execute(
                """UPDATE backend.processes SET heartbeat_at = now() WHERE uuid = %s""",
                (self.uuid,),
            )
            self.conn.commit()
            self.heartbeat_at = t

    def get_api_response(self):
        return self.conn.execute(
            """
            SELECT *
            FROM backend.api_requests
            WHERE requested_at IS NOT NULL
              AND completed_at IS NULL
            ORDER BY priority DESC, created_at ASC
            LIMIT 1
            """
        ).fetchone()

    def get_action(self, action_id=None):
        if action_id is not None:
            action = self.conn.execute(
                """
                SELECT *
                FROM backend.actions
                WHERE is = %s
                """,
                (action_id, )
            ).fetchone()
        else:
            action = self.conn.execute(
                """
                SELECT *
                FROM backend.actions
                WHERE ready_at <= now()
                ORDER BY priority DESC, created_at ASC
                LIMIT 1
                """
            ).fetchone()
        return action

    def update_game(self, api_response):
        pass

    def update_action(self, api_response=None, action=None):
        now = time.now()
        # action completed
        if api_response:
            # TODO: get all relevant cooldowns
            plan_id = self.conn.execute(
                """
                UPDATE backend.actions 
                SET
                    completed_at = %s
                WHERE id = %s
                RETURNING plan_id
                """,
                (now, api_response["action_id"],)
            ).fetchone()[0]
            cd = api_response["response_json"]["data"].get("cooldown", now)
            if time.remaining(cd) == 0:
                return plan_id
        # action accepted
        if action:
            self.conn.execute(
                """
                UPDATE backend.actions 
                SET
                    accepted_at = %s
                WHERE id = %s
                """,
                (now, action["id"],)
            ).fetchone()
        return None

    def update_plan(self, plan_id, cooldown):
        # mark plan progress + get next_action_id
        # TODO: how to link actions together?
        # TODO: how to wait for the last action to be completed (including cooldown)?
        next_action_id = None
        if next_action_id:
            # set next action ready_at
            self.conn.execute(
                """
                UPDATE backend.actions
                SET
                    ready_at = %s
                WHERE id = %s
                """,
                (cooldown, next_action_id)
            )
        else:
            # mark plan completed and return goal_id
            goal_id = self.conn.execute(
                """
                UPDATE backend.plans
                SET
                    completed_at = %s
                WHERE id = %s
                RETURNING goal_id
                """,
                (cooldown, plan_id)
            ).fetchone()[0]
            return goal_id
        return None

if __name__ == "__main__":
    m = Worker(uuid=argv[1])
