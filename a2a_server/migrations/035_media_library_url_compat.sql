-- Migration 035: media library URL compatibility
--
-- /orpc/media/library/list (listMedia) projects a `url` column. Some existing
-- databases have a media_library table created before that projection existed,
-- which makes the endpoint fail with: column "url" does not exist.

BEGIN;

ALTER TABLE IF EXISTS media_library
  ADD COLUMN IF NOT EXISTS url TEXT;

DO $$
DECLARE
  source_column TEXT;
BEGIN
  IF to_regclass('media_library') IS NULL THEN
    RETURN;
  END IF;

  FOREACH source_column IN ARRAY ARRAY[
    'public_url',
    'storage_url',
    'object_url',
    'file_url',
    'source_url',
    'path'
  ] LOOP
    IF EXISTS (
      SELECT 1
      FROM information_schema.columns
      WHERE table_schema = current_schema()
        AND table_name = 'media_library'
        AND column_name = source_column
    ) THEN
      EXECUTE format(
        'UPDATE media_library SET url = %1$I WHERE url IS NULL AND %1$I IS NOT NULL',
        source_column
      );
    END IF;
  END LOOP;
END $$;

COMMIT;
