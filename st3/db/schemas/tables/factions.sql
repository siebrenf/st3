CREATE TABLE factions
(
    "symbol" text PRIMARY KEY,
    "name" text,
    "description" text,
    "headquarters" text,
    "traits" text[],
    "isRecruiting" bool
);