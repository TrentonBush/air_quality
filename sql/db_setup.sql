-- dcl
GRANT SELECT ON public.air_quality TO grafanareader;
-- ddl
CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS sensor_data (
    time timestamptz NOT NULL,
    temp double precision,
    press double precision
);

SELECT create_hypertable('sensor_data', 'time');
