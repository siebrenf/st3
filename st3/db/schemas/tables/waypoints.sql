CREATE TABLE waypoints
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