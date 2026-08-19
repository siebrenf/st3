CREATE TABLE game.market_transactions
(
    "id" BIGINT GENERATED ALWAYS AS IDENTITY UNIQUE,
    "waypointSymbol" text,
    "systemSymbol" text,
    "shipSymbol" text,
    "tradeSymbol" text,
    "type" text,
    "units" integer,
    "pricePerUnit" integer,
    "totalPrice" integer,
    "timestamp" timestamptz
);