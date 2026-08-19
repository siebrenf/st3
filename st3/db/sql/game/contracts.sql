CREATE TABLE game.contracts
(
    "id" text PRIMARY KEY,
    "agentSymbol" text,
    "factionSymbol" text,
    "type" text,  -- PROCUREMENT/TRANSPORT/SHUTTLE
    "terms" JsonB,
    "accepted" bool,
    "fulfilled" bool,
    "deadlineToAccept" timestamptz
);
CREATE INDEX game.contracts_agentSymbol_deadlineToAccept_idx
ON game.contracts ("agentSymbol", "deadlineToAccept");