CREATE TABLE api_requests (
    -- request
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    agent            text REFERENCES agents(symbol),
    method           text NOT NULL, --get/post/patch
    endpoint         text NOT NULL, --suffix only
    json             JsonB,
    params           JsonB,

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