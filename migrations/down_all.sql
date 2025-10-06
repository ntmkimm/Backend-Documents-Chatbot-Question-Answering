-- Rollback everything

-- chat memory
DROP TABLE IF EXISTS lc_message_history CASCADE;
DROP TABLE IF EXISTS checkpoint_writes CASCADE;
DROP TABLE IF EXISTS checkpoint_blobs CASCADE;
DROP TABLE IF EXISTS checkpoints CASCADE;
DROP TABLE IF EXISTS checkpoint_migrations CASCADE;

-- all relations to source / notebook
DROP TABLE IF EXISTS open_notebook_default_prompts CASCADE;
DROP TABLE IF EXISTS transformation CASCADE;
DROP TABLE IF EXISTS chat_session CASCADE;
DROP TABLE IF EXISTS source_insight CASCADE;
DROP TABLE IF EXISTS source_embedding_ids CASCADE;
DROP TABLE IF EXISTS source CASCADE;
DROP TABLE IF EXISTS notebook CASCADE;

DROP TABLE IF EXISTS _sbl_migrations CASCADE;



-- Optionally drop extension if you want bare DB
-- DROP EXTENSION IF EXISTS "pgcrypto";
