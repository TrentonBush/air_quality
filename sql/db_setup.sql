-- dcl
GRANT SELECT ON public.air_quality TO grafanareader;
-- ddl
CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS sensor_data (
    time timestamptz NOT NULL,
    temp real,
    press double precision,
    humidity real,
    temp_hdc real,
    -- No unsigned ints in PG so I have to use 32 bits for uint16 values.
    -- Won't matter after delta compression though
    eco2 int,
    tvoc int,
    baseline int,
    current smallint, -- 6 bits unsigned
    voltage real,
    co2 smallint -- 16 bits but range is 400 to 10000
);

SELECT create_hypertable('sensor_data', 'time');
