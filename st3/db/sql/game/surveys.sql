CREATE TABLE game.surveys
(
    "signature" text PRIMARY KEY,
    "symbol" text,
    "deposits" JsonB,
    "expiration" timestamptz,
    "size" text  --SMALL/MODERATE/LARGE
);
CREATE INDEX game.surveys_symbol_idx ON game.surveys("symbol");
CREATE INDEX game.surveys_expiration_idx ON game.surveys("expiration");