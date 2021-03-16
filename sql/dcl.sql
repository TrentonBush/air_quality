-- Grafana setup - read only user
CREATE USER grafanareader WITH PASSWORD 'grafana';
GRANT USAGE ON SCHEMA public TO grafanareader;
-- connect to db, eg \c air_quality
GRANT SELECT ON public.air_quality TO grafanareader;
