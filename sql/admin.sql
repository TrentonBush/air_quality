-- ddl
CREATE DATABASE air_quality;
ALTER DATABASE air_quality SET timezone = 'America/Los_Angeles';
-- dcl
-- Grafana setup - read only user
CREATE USER grafanareader WITH PASSWORD 'grafana';
GRANT USAGE ON SCHEMA public TO grafanareader;