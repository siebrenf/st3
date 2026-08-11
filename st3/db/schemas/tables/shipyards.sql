CREATE TABLE shipyards
(
    "symbol" text PRIMARY KEY,
    "systemSymbol" text,
    "shipTypes" text[],
    "modificationsFee" integer
);