CREATE TABLE backend.api_requests (
    -- queue
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    action_id        bigint REFERENCES backend.actions(id),
    priority         integer NOT NULL DEFAULT 0,
    created_at       timestamptz NOT NULL DEFAULT now(),
    requested_at     timestamptz,
    completed_at     timestamptz,

    -- request
    agent            text REFERENCES game.agents(symbol),
    method           text NOT NULL, --get/post/patch
    endpoint         text NOT NULL, --suffix only
    json             JsonB,
    params           JsonB,

    -- response
    response_status  integer,
    response_headers JsonB,
    response_json    JsonB
);
CREATE INDEX backend.api_requests_queue_idx
ON backend.api_requests (priority DESC, created_at ASC)
WHERE requested_at IS NULL;
CREATE INDEX backend.api_requests_processing_idx
ON backend.api_requests (priority DESC, created_at ASC)
WHERE requested_at IS NOT NULL
  AND completed_at IS NULL;