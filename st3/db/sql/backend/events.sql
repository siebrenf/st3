CREATE TABLE backend.events (
    msg         text NOT NULL,
    level       text NOT NULL DEFAULT info,
    time        timestamptz NOT NULL DEFAULT now()
);