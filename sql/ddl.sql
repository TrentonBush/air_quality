CREATE DATABASE air_quality;
ALTER DATABASE air_quality SET timezone = 'America/Los_Angeles';
-- connect to db, eg \c air_quality

CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS sensor_data (
    time timestamptz NOT NULL,
    temp double PRECISION,
    press double PRECISION
);

SELECT create_hypertable('sensor_data', 'time');
