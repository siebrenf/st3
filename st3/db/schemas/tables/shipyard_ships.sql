CREATE TABLE shipyard_ships
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