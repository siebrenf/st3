CREATE TABLE game.ships
(
    "symbol" text PRIMARY KEY,
    "agentSymbol" text,
    "nav" JsonB,
    "crew" JsonB,
    "fuel" JsonB,
    "cooldown" JsonB,
    "frame" JsonB,
    "reactor" JsonB,
    "engine" JsonB,
    "modules" JsonB,
    "mounts" JsonB,
    "registration" JsonB,
    "cargo" JsonB
);
CREATE INDEX game.ships_agentSymbol_idx ON game.ships("agentSymbol");
CREATE INDEX game.ships_nav_systemSymbol_idx ON game.ships ((nav ->> 'systemSymbol'));