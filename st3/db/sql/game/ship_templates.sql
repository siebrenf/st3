CREATE TABLE game.ship_templates
(
    "type" text PRIMARY KEY,
    "name" text,
    "description" text,
    "frame" JsonB,
    "reactor" JsonB,
    "engine" JsonB,
    "modules" JsonB,
    "mounts" JsonB,
    "crew" JsonB
);