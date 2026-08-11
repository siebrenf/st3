CREATE TABLE market_tradegoods
(
    "id" BIGINT GENERATED ALWAYS AS IDENTITY UNIQUE,
    "waypointSymbol" text,
    "systemSymbol" text,
    "symbol" text,
    "tradeVolume" integer,
    "type" text,  --IMPORT/EXPORT/EXCHANGE
    "supply" text,  --SCARCE/LIMITED/MODERATE/HIGH/ABUNDANT
    "activity" text,  --WEAK/GROWING/STRONG/RESTRICTED
    "purchasePrice" integer,
    "sellPrice" integer,
    "timestamp" timestamptz
);