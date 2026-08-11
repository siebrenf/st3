CREATE TABLE shipyard_transactions
(
    "id" BIGINT GENERATED ALWAYS AS IDENTITY UNIQUE,
    "waypointSymbol" text,
    "systemSymbol" text,
    "shipSymbol" text,
    "agentSymbol" text,
    "shipType" text,
    "price" integer,
    "timestamp" timestamptz
);