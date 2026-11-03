-- The Streamlit app's read-only database login.
--
-- Run once, by hand, in the Supabase SQL editor, after applying
-- schema.sql (which creates app_viewers). Replace the password first and
-- don't save it back into this file: it goes only into the app's Secrets.
-- This is the one exception to "never use the SQL editor": a role's
-- password can't live in a versioned file, and CREATE ROLE can't be made
-- idempotent in plain SQL, so it stays out of schema.sql.
--
-- On Supabase's pooler the login name is app_reader.<project ref>, the
-- same pattern as the postgres user in .env.

CREATE ROLE app_reader LOGIN PASSWORD 'replace-with-a-long-random-password';

-- Everything below is safe to re-run. Re-run it after giving the app a
-- new view or table to read: new objects are NOT granted automatically,
-- on purpose, so a new raw table never becomes readable by accident.

GRANT USAGE ON SCHEMA public TO app_reader;

-- Views and summary tables the app charts. Deliberately absent: duro (read
-- through duro_filtered instead) and observations (volunteer submissions).
GRANT SELECT ON cwqt, turbidity_rta1, turbidity_rta2, turbidity,
                duro_filtered, site_zones, daily_site_summary,
                daily_weather, rain_windows
             TO app_reader;

-- Supabase turns on row-level security for tables, and with it on a
-- GRANT alone returns zero rows, with no error. Each table the app reads
-- directly also needs a policy. (Views run with their owner's rights, so
-- they don't.)
DROP POLICY IF EXISTS app_reader_reads ON cwqt;
CREATE POLICY app_reader_reads ON cwqt FOR SELECT TO app_reader USING (true);
DROP POLICY IF EXISTS app_reader_reads ON turbidity_rta1;
CREATE POLICY app_reader_reads ON turbidity_rta1 FOR SELECT TO app_reader USING (true);
DROP POLICY IF EXISTS app_reader_reads ON turbidity_rta2;
CREATE POLICY app_reader_reads ON turbidity_rta2 FOR SELECT TO app_reader USING (true);

GRANT SELECT ON app_viewers TO app_reader;
DROP POLICY IF EXISTS app_reader_reads_viewers ON app_viewers;
CREATE POLICY app_reader_reads_viewers ON app_viewers FOR SELECT TO app_reader USING (true);
