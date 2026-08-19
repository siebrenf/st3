CREATE TABLE game.shipyard_ships
(
    "id" BIGINT GENERATED ALWAYS AS IDENTITY UNIQUE,
    "waypointSymbol" text,
    "systemSymbol" text,
    "type" text, --shipType
    "supply" text,  --SCARCE/LIMITED/MODERATE/HIGH/ABUNDANT
    "activity" text,  --WEAK/GROWING/STRONG/RESTRICTED
    "purchasePrice" integer,
    "timestamp" timestamptz
);
CREATE INDEX game.shipyard_ships_type_idx ON game.shipyard_ships("type");
CREATE INDEX game.shipyard_ships_systemSymbol_idx ON game.shipyard_ships("systemSymbol");
CREATE INDEX game.shipyard_ships_timestamp_idx ON game.shipyard_ships("timestamp");