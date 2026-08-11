-- sectorSymbol text, always X1
-- factions JSONB, always empty
CREATE TABLE systems
(
    symbol text PRIMARY KEY,
    type text,
    x integer,
    y integer
);