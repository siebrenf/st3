CREATE TABLE game.markets
(
    "symbol" text PRIMARY KEY,
    "systemSymbol" text,
    "imports" text[],
    "exports" text[],
    "exchange" text[]
);
CREATE INDEX game.markets_systemSymbol_idx ON game.markets("systemSymbol");