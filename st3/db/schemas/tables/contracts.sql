CREATE TABLE contracts
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