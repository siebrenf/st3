CREATE TABLE markets
(
    "symbol" text PRIMARY KEY,
    "systemSymbol" text,
    "imports" text[],
    "exports" text[],
    "exchange" text[]
);