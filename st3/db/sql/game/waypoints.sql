CREATE TABLE game.waypoints
(
    "symbol" text PRIMARY KEY,
    "systemSymbol" text,
    "type" text,
    "x" integer,
    "y" integer,
    "orbits" text,
    "orbitals" text[],
    "traits" text[],
    "chart" JSONB,
    "faction" text,
    "isUnderConstruction" bool
);
CREATE INDEX game.waypoints_systemSymbol_idx ON game.waypoints("systemSymbol");