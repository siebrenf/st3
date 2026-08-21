CREATE TABLE backend.actions (
    -- queue
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    plan_id          bigint REFERENCES backend.plans(id),
    priority         integer NOT NULL DEFAULT 0,
    created_at       timestamptz NOT NULL DEFAULT now(),
    ready_at         timestamptz,  -- when this action is ready to be accepted
    accepted_at      timestamptz,
    completed_at     timestamptz,

    -- action
    action           text NOT NULL,
    md               JsonB,
);
CREATE INDEX backend.actions_queue_idx
ON backend.actions (ready_at, priority DESC, created_at ASC);