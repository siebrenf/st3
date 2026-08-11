INSERT INTO workers (key, value)
VALUES
    ('messengers', to_jsonb(1)),
    ('directors', to_jsonb(1)),
    ('workers', to_jsonb(1)),
    ('reset', to_jsonb(false)),
    ('shutdown', to_jsonb(false));