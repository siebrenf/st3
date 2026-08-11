from psycopg import connect
from contextlib import contextmanager


@contextmanager
def _connection(session, conn=None):
    if conn is not None:
        yield conn
    else:
        with connect(f"dbname={session} user=postgres") as conn:
            yield conn


def get_session(conn=None):
    with _connection("st3", conn) as conn:
        _, last_reset, next_reset = conn.execute(
            """SELECT * FROM sessions WHERE "session" = 'current'"""
        ).fetchone()
    session = f"{last_reset}_{next_reset[:10]}"
    return session


def get_token(agent, session, conn=None):
    with _connection(session, conn) as conn:
        return conn.execute(
            'SELECT "token" FROM agents WHERE "symbol" = %s',
            (agent,)
        ).fetchone()[0]
