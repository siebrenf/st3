CREATE TABLE game.jump_gates
(
    "symbol" text PRIMARY KEY,
    "systemSymbol" text,
    "connections" text[]
);
CREATE INDEX game.jump_gates_systemSymbol_idx ON game.jump_gates("systemSymbol");