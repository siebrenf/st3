CREATE TABLE backend.cpu_usage (
    uuid        uuid NOT NULL,
    cpu_usage   real NOT NULL,
    time        timestamptz NOT NULL DEFAULT now()
);