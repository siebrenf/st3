CREATE TABLE api_requests (
    -- request
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    method           text NOT NULL, --get/post/patch
    endpoint         text NOT NULL,
    headers          JsonB,
    json             JsonB,

    -- queue
    priority         integer NOT NULL DEFAULT 0,
    completed        boolean NOT NULL DEFAULT false,
    created_at       timestamptz NOT NULL DEFAULT now(),
    completed_at     timestamptz,

    -- response
    response_status  integer,
    response_headers JsonB,
    response_json    JsonB
);