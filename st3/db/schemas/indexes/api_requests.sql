CREATE INDEX api_requests_queue_idx
ON api_requests (priority DESC, id ASC)  -- higher priority + lower ID comes first
WHERE completed = false;