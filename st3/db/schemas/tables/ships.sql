CREATE TABLE ships
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