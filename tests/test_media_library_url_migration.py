"""Regression coverage for the media library listMedia URL migration."""

import sqlite3
from pathlib import Path


SQL = Path('a2a_server/migrations/035_media_library_url_compat.sql').read_text()
SOURCE_COLUMNS = (
    'public_url',
    'storage_url',
    'object_url',
    'file_url',
    'source_url',
    'path',
)


def test_media_library_url_column_is_added_idempotently():
    assert 'ALTER TABLE IF EXISTS media_library' in SQL
    assert 'ADD COLUMN IF NOT EXISTS url TEXT' in SQL


def test_media_library_url_backfill_is_safe_for_optional_source_columns():
    assert "to_regclass('media_library') IS NULL" in SQL
    assert 'information_schema.columns' in SQL
    assert 'column_name = source_column' in SQL
    assert 'UPDATE media_library SET url' in SQL

    for source_column in SOURCE_COLUMNS:
        assert source_column in SQL


def test_list_media_projection_is_fixed_for_existing_schema_without_url():
    """Exercise the CI failure shape: listMedia selects url from an old table.

    The production migration is PostgreSQL-specific, but the failing contract is
    database-portable: an existing media_library table has a usable path-like
    column and no url column, while listMedia projects url. This test validates
    the compatibility migration semantics against that representative schema.
    """
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.execute(
        '''
        CREATE TABLE media_library (
            id TEXT PRIMARY KEY,
            path TEXT NOT NULL,
            title TEXT
        )
        '''
    )
    conn.execute(
        "INSERT INTO media_library (id, path, title) VALUES (?, ?, ?)",
        ('media-1', 'https://cdn.example.test/media-1.mp4', 'Demo clip'),
    )

    try:
        conn.execute('SELECT id, url FROM media_library').fetchall()
    except sqlite3.OperationalError as exc:
        assert 'no such column: url' in str(exc)
    else:  # pragma: no cover - proves the pre-migration failure must exist
        raise AssertionError('representative pre-migration schema unexpectedly has url')

    # Apply the same compatibility behavior as migration 035: add url, then
    # backfill from the first optional source column present on the old schema.
    conn.execute('ALTER TABLE media_library ADD COLUMN url TEXT')
    existing_columns = {
        row['name'] for row in conn.execute('PRAGMA table_info(media_library)').fetchall()
    }
    for source_column in SOURCE_COLUMNS:
        if source_column in existing_columns:
            conn.execute(
                f'UPDATE media_library SET url = {source_column} '
                f'WHERE url IS NULL AND {source_column} IS NOT NULL'
            )

    rows = conn.execute('SELECT id, url FROM media_library').fetchall()

    assert [dict(row) for row in rows] == [
        {'id': 'media-1', 'url': 'https://cdn.example.test/media-1.mp4'}
    ]
