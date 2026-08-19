CREATE TABLE game.market_tradegoods
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
CREATE INDEX game.market_tradegoods_symbol_idx ON game.market_tradegoods("symbol");
CREATE INDEX game.market_tradegoods_systemSymbol_idx ON game.market_tradegoods("systemSymbol");
CREATE INDEX game.market_tradegoods_timestamp_idx ON game.market_tradegoods("timestamp");