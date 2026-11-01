-- The least-privilege login the website runs as (the user in DATABASE_URL). Run it as the database
-- owner after the migrations, and again after any migration that adds a table; running it twice is
-- safe. It is one statement, so it also works in editors that run one statement at a time (Vercel's
-- Storage > Query). The password is set separately and never stored here:
--   ALTER ROLE llmslim_app WITH PASSWORD '...';
-- CI runs the end-to-end tests as this role, and the test setup fails if a table has no grant here.
DO $role$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'llmslim_app') THEN
    CREATE ROLE llmslim_app WITH LOGIN;
  END IF;
  EXECUTE format('GRANT CONNECT ON DATABASE %I TO llmslim_app', current_database());
  GRANT USAGE ON SCHEMA public TO llmslim_app;
  GRANT SELECT, INSERT, UPDATE, DELETE ON "user", session, account, verification, passkey, rate_limit TO llmslim_app;
  -- The audit trail can be written and pruned, never edited.
  GRANT SELECT, INSERT, DELETE ON auth_event TO llmslim_app;
END
$role$;
