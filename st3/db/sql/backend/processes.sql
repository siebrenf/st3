CREATE TABLE backend.processes (
    uuid            uuid PRIMARY KEY,
    pid             text NOT NULL,
    role            text NOT NULL,
    agent           text,
    started_at      timestamptz NOT NULL DEFAULT now(),
    stopped_at      timestamptz,
    heartbeat_at  timestamptz NOT NULL DEFAULT now(),
);