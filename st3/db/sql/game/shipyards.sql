CREATE TABLE game.shipyards
(
    "symbol" text PRIMARY KEY,
    "systemSymbol" text,
    "shipTypes" text[],
    "modificationsFee" integer
);
CREATE INDEX game.shipyards_systemSymbol_idx ON game.shipyards("systemSymbol");