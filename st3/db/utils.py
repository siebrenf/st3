from contextlib import contextmanager

from psycopg import connect

from st3.time import read


def get_session(return_next=False):
    with connect("dbname=st3 user=postgres") as conn:
        _, last_reset, next_reset = conn.execute(
            """SELECT * FROM sessions WHERE "session" = 'current'"""
        ).fetchone()
    session = f"{last_reset}_{next_reset[:10]}"
    if return_next:
        return session, read(next_reset)
    return session


@contextmanager
def connect_simple(session, conn=None):
    if conn is not None:
        yield conn
    else:
        with connect(f"dbname={session} user=postgres") as conn:
            yield conn


def get_token(agent, session=None, conn=None):
    if session is None:
        session = get_session()
    with connect_simple(session, conn) as conn:
        return conn.execute(
            'SELECT "token" FROM agents WHERE "symbol" = %s', (agent,)
        ).fetchone()[0]
