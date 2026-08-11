CREATE INDEX ships_agentSymbol_idx ON ships("agentSymbol");
CREATE INDEX ships_nav_systemSymbol_idx ON ships ((nav ->> 'systemSymbol'));