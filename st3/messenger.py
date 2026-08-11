from psycopg import connect
from psycopg.rows import dict_row
from st3.db.utils import get_session
from st3.request import Request


"""
SELECT *
FROM api_requests
WHERE completed = false
ORDER BY priority DESC, id ASC
LIMIT 1;
"""

# TODO: on server reset:
#  - UPDATE workers (value) WHERE key = 'reset' (to_jsonb(true),);
#  - wait for the end


class Messenger:
    def __init__(self):
        self.session = get_session()
        self.request = Request()

        while True:
            # TODO: LISTEN for queue activity
            with connect(f"dbname={self.session} user=postgres", row_factory=dict_row) as conn:
                api_request = conn.execute(
                    """
                    SELECT *
                    FROM api_requests
                    WHERE completed = false
                    ORDER BY priority DESC, id ASC
                    LIMIT 1;
                    """
                ).fetchone()

            # TODO: rewrite request logic
            ret = self.request(
                method=api_request["method"],
                endpoint=api_request["endpoint"],
                headers=api_request["headers"],
                json=api_request["json"],
                params=api_request["params"],
            )

            response_status = ret.status_code
            response_headers = ret.headers
            response_json = ret.json()

            with connect(f"dbname={self.session} user=postgres") as conn:
                conn.execute(
                    """
                    UPDATE api_requests
                    SET completed = true,
                     completed_at = now(),
                     response_status = %s,
                     response_headers = %s,
                     response_json = %s
                    WHERE id = %s
                    """,
                    (response_status, response_headers, response_json, api_request["id"])
                )
