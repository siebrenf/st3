import subprocess as sp
from pathlib import Path

import requests
from psycopg import connect, sql

from st3 import DATA_DIR
from st3.logging import logger


class DataBase:
    """
    Controls the creation and destruction of the st3 and session database.
    This class is intended for the Supervisor and the user only.
    """

    def __init__(self, debug=False):
        # set up the SQL server
        self.path = DATA_DIR / "sql"
        self.log = DATA_DIR / "sql_log.txt"
        self.sql_dir = Path(__file__).parent / "sql"
        self.debug = debug

        if not self.path.is_dir():
            self._init_server()

        # set up the session database
        if not self.is_running():
            self.start()
        self.session = self._get_session()

        if not self.exists():
            self._create()

        # generate tables & indexes
        self._populate_db()

    def _init_server(self):
        """create the SQL server"""
        if self.debug:
            logger.debug("Initializing SQL server")
        sp.run(
            f"initdb --username=postgres {self.path}",
            shell=True,
            check=True,
            capture_output=True,
        )

    def is_running(self):
        """check if the SQL server is running"""
        # check=False because an offline server returns exit code 3
        ret = sp.run(
            f"pg_ctl -D {self.path} status",
            shell=True,
            check=False,
            capture_output=True,
        )
        if ret.returncode == 0:
            running = True
        elif ret.returncode == 3:
            running = False
        else:
            code = ret.returncode
            out = ret.stdout.decode().strip()
            err = ret.stderr.decode().strip()
            raise NotImplementedError(
                f"Error code: {code}, stdout: {out}, stderr: {err}"
            )
        return running

    def start(self):
        if self.debug:
            logger.debug("Starting SQL server")
        sp.run(
            f"pg_ctl -D {self.path} -l {self.log} start",
            shell=True,
            check=True,
            capture_output=True,
        )

    def stop(self):
        if self.debug:
            logger.debug("Stopping SQL server")
        sp.run(
            f"pg_ctl -D {self.path} stop", shell=True, check=True, capture_output=True
        )

    def _get_session(self):
        status = requests.get("https://api.spacetraders.io/v2/").json()
        if (
            status.get("status")
            != "SpaceTraders is currently online and available to play"
        ):
            raise RuntimeError(status)

        last_reset = status["resetDate"]
        next_reset = status["serverResets"]["next"]
        session = f"{last_reset}_{next_reset[:10]}"

        # save the session in the st3.sessions table
        # and update the "current" session with the same details
        if not self.exists("st3"):
            self._create("st3")
        with connect("dbname=st3 user=postgres") as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session text PRIMARY KEY,
                    last_reset text,
                    next_reset text
                )
                """)
            conn.execute(
                """
                INSERT INTO sessions (session, last_reset, next_reset)
                VALUES (%s, %s, %s)
                ON CONFLICT (session) DO NOTHING
                """,
                (session, last_reset, next_reset),
            )
            conn.execute(
                """
                INSERT INTO sessions (session, last_reset, next_reset)
                VALUES (%s, %s, %s)
                ON CONFLICT (session) DO UPDATE
                SET last_reset = EXCLUDED.last_reset, next_reset = EXCLUDED.next_reset
                """,
                ("current", last_reset, next_reset),
            )

        return session

    def exists(self, session=None):
        """check if a database exists"""
        if session is None:
            session = self.session
        with connect("dbname=postgres user=postgres") as conn:
            return conn.execute(
                """
                SELECT EXISTS (
                    SELECT FROM pg_database
                    WHERE datname = %s
                )
                """,
                (session,),
            ).fetchone()[0]

    def _create(self, session=None):
        """create a database"""
        if session is None:
            session = self.session
        if self.debug:
            logger.debug(f"Creating database {session}")
        sp.run(
            f"createdb --no-password --owner=postgres --user=postgres {session}",
            shell=True,
            check=True,
            capture_output=True,
        )

        # match the timezone with the server
        with connect("dbname=postgres user=postgres") as conn:
            conn.execute(
                sql.SQL("ALTER DATABASE {} SET timezone TO 'UTC'").format(
                    sql.Identifier(session)
                )
            )

    @staticmethod
    def list_all_dbs():
        with connect("dbname=postgres user=postgres") as conn:
            cur = conn.execute("""
                SELECT datname
                FROM pg_catalog.pg_database
                ORDER BY datname
                """)
            return [row[0] for row in cur.fetchall()]

    def list_schemas(self, session=None):
        if session is None:
            session = self.session
        with connect(f"dbname={session} user=postgres") as conn:
            cur = conn.execute(
                """
                SELECT nspname AS schema_name
                FROM pg_catalog.pg_namespace
                WHERE nspname NOT LIKE 'pg_%'
                  AND nspname <> 'information_schema'
                ORDER BY nspname;
                """,
            )
            return [row[0] for row in cur.fetchall()]

    def list_schema_tables(self, schema):
        with connect(f"dbname={self.session} user=postgres") as conn:
            cur = conn.execute(
                """
                SELECT tablename
                FROM pg_catalog.pg_tables
                WHERE schemaname = %s
                ORDER BY tablename;
                """,
                (schema,),
            )
            return [row[0] for row in cur.fetchall()]

    # def list_tables(self):
    #     with connect(f"dbname={self.session} user=postgres") as conn:
    #         cur = conn.execute(
    #             """
    #             SELECT table_name
    #             FROM information_schema.tables
    #             WHERE table_schema = 'public'
    #             """
    #         )
    #         return [row[0] for row in cur.fetchall()]
    #
    # def list_indexes(self):
    #     with connect(f"dbname={self.session} user=postgres") as conn:
    #         cur = conn.execute(
    #             """
    #             SELECT indexname
    #             FROM pg_indexes
    #             """
    #         )
    #         return [row[0] for row in cur.fetchall()]
    #
    # def list_views(self):
    #     with connect(f"dbname={self.session} user=postgres") as conn:
    #         cur = conn.execute(
    #             """
    #             SELECT viewname
    #             FROM pg_catalog.pg_views
    #             WHERE schemaname = 'public'
    #             """
    #         )
    #         return [row[0] for row in cur.fetchall()]

    def _populate_db(self):
        """Create all missing table and their associated indexes"""
        all_schemas = ["backend", "game"]
        all_tables = {
            "backend": ["api_requests", "events", "supervisor"],
            "game": [
                "agents",
                "agents_public",
                "contracts",
                "events",
                "factions",
                "jump_gates",
                "market_tradegoods",
                "market_transactions",
                "markets",
                "ship_templates",
                "ships",
                "shipyard_ships",
                "shipyard_transactions",
                "shipyards",
                "surveys",
                "systems",
                "traits_faction",
                "traits_waypoint",
                "waypoints",
            ],
        }
        with connect(f"dbname={self.session} user=postgres") as conn:
            found_schemas = self.list_schemas()
            for schema in all_schemas:
                if schema not in found_schemas:
                    if self.debug:
                        logger.debug(f"Creating {schema=}")
                    sql_file = self.sql_dir / "schemas" / f"{schema}.sql"
                    conn.execute(sql.SQL(sql_file.read_text()))  # noqa

                found_tables = self.list_schema_tables(schema)
                for table in all_tables[schema]:
                    if table not in found_tables:
                        if self.debug:
                            logger.debug(f"Creating {table=}")
                        sql_file = self.sql_dir / schema / f"{table}.sql"
                        conn.execute(sql.SQL(sql_file.read_text()))  # noqa

        # tables = self.list_tables()
        # with connect(f"dbname={self.session} user=postgres") as conn:
        #     for table in sorted((self.schema_dir / "tables").iterdir()):
        #         if table.stem not in tables:
        #             if self.debug:
        #                 logger.debug(f"Creating table {table.stem}")
        #             conn.execute(sql.SQL(table.read_text()))
        #
        #             index = self.schema_dir / "indexes" / table.name
        #             if index.exists():
        #                 if self.debug:
        #                     logger.debug(f"Creating index {index.stem}")
        #                 conn.execute(sql.SQL(index.read_text()))
        #
        #             default = self.schema_dir / "defaults" / table.name
        #             if default.exists():
        #                 if self.debug:
        #                     logger.debug(f"Inserting default into {default.stem}")
        #                 conn.execute(sql.SQL(default.read_text()))

    def drop(self, name, kind: str = "table"):
        """drop a table, index or view"""
        if self.debug:
            logger.debug(f"Dropping {kind} {name}")
        with connect(f"dbname={self.session} user=postgres") as conn:
            if kind == "table":
                conn.execute("""DROP TABLE IF EXISTS %s CASCADE""", (name,))
            elif kind == "index":
                conn.execute("""DROP INDEX IF EXISTS %s CASCADE""", (name,))
            elif kind == "view":
                conn.execute("""DROP VIEW IF EXISTS %s CASCADE""", (name,))
            else:
                raise TypeError(kind)

    def delete_db(self, session=None):
        """Destroy a specified session database (default: current session)"""
        if session is None:
            session = self.session
        with connect("dbname=postgres user=postgres", autocommit=True) as conn:
            conn.execute(
                sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(session))
            )

    def restart(self):
        self.session = self._get_session()

        if not self.exists():
            self._create()

        # generate tables & indexes
        self._populate_db()

    # def delete_server(self):
    #     """The nuclear option"""
    #     if self.is_running():
    #         self.stop()
    #     if self.path.is_dir():
    #         if self.debug:
    #             logger.debug(f"Deleting {self.path}")
    #         shutil.rmtree(self.path)
    #         self.log.unlink()
