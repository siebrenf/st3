CREATE TABLE backend.supervisor (
    key         text PRIMARY KEY,
    value       jsonb NOT NULL,
    updated_at  timestamptz NOT NULL DEFAULT now()
);
INSERT INTO backend.supervisor (key, value)
VALUES
    ('workers', to_jsonb(1)),
    ('reset', to_jsonb(false)),
    ('shutdown', to_jsonb(false));