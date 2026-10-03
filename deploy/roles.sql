CREATE ROLE tt_owner LOGIN PASSWORD 'CHANGE_ME_OWNER' BYPASSRLS;
CREATE ROLE tt_app NOLOGIN;
CREATE ROLE tt_worker NOLOGIN;
CREATE ROLE tt_ops NOLOGIN;
CREATE ROLE web LOGIN PASSWORD 'CHANGE_ME_WEB' IN ROLE tt_app;
CREATE ROLE worker LOGIN PASSWORD 'CHANGE_ME_WORKER' IN ROLE tt_worker;
CREATE ROLE ops LOGIN PASSWORD 'CHANGE_ME_OPS' IN ROLE tt_ops;

ALTER ROLE web SET statement_timeout = '5s';
ALTER ROLE web SET lock_timeout = '2s';
ALTER ROLE worker SET statement_timeout = '120s';
ALTER ROLE ops SET statement_timeout = '600s';

CREATE DATABASE timetable OWNER tt_owner;
\connect timetable
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO tt_app, tt_worker, tt_ops;
GRANT ALL ON SCHEMA public TO tt_owner;
