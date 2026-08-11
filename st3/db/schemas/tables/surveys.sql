CREATE TABLE surveys
(
    "signature" text PRIMARY KEY,
    "symbol" text,
    "deposits" JsonB,
    "expiration" timestamptz,
    "size" text  --SMALL/MODERATE/LARGE
);