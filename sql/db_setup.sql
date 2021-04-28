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
    co2 smallint, -- range is 400 to 10000
    pm1_0 smallint,
    pm2_5 smallint,
    pm10_0 smallint,
    pm1_0_atm smallint,
    pm2_5_atm smallint,
    pm10_0_atm smallint,
    count_0_3 int,
    count_0_5 int,
    count_1_0 int,
    count_2_5 int,
    count_5_0 int,
    count_10_0 int
);

SELECT create_hypertable('sensor_data', 'time');
