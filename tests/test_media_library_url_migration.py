"""Regression coverage for the media library listMedia URL migration."""

from pathlib import Path


SQL = Path('a2a_server/migrations/035_media_library_url_compat.sql').read_text()


def test_media_library_url_column_is_added_idempotently():
    assert 'ALTER TABLE IF EXISTS media_library' in SQL
    assert 'ADD COLUMN IF NOT EXISTS url TEXT' in SQL


def test_media_library_url_backfill_is_safe_for_optional_source_columns():
    assert "to_regclass('media_library') IS NULL" in SQL
    assert 'information_schema.columns' in SQL
    assert 'column_name = source_column' in SQL
    assert 'UPDATE media_library SET url' in SQL

    for source_column in (
        'public_url',
        'storage_url',
        'object_url',
        'file_url',
        'source_url',
        'path',
    ):
        assert source_column in SQL
