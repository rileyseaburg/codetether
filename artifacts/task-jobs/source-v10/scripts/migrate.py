#!/usr/bin/env python3
"""
Database migration script for A2A Server.

Usage:
    python scripts/migrate.py              # Run migrations using DATABASE_URL from .env
    python scripts/migrate.py --dev        # Run migrations on dev database
    python scripts/migrate.py --prod       # Run migrations on prod database
    python scripts/migrate.py --url <url>  # Run migrations on specific database URL
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env before importing database module
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / '.env')


async def run_migrations(database_url: str) -> bool:
    """Run database migrations."""
    # Override DATABASE_URL for this process
    os.environ['DATABASE_URL'] = database_url

    # Import after setting DATABASE_URL
    from a2a_server.database import _init_schema, get_pool

    print(
        f'Connecting to: {database_url.split("@")[1] if "@" in database_url else database_url}'
    )

    try:
        # Initialize schema (creates tables if they don't exist)
        await _init_schema()
        print('Schema initialized successfully.')

        # Verify connection and list tables
        pool = await get_pool()
        async with pool.acquire() as conn:
            tables = await conn.fetch(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
            )
            print(f'\nTables ({len(tables)}):')
            for t in tables:
                print(f'  - {t["tablename"]}')

        return True
    except Exception as e:
        print(f'Migration failed: {e}')
        return False


def get_database_url(args) -> str:
    """Determine database URL from arguments."""
    base_url = os.getenv('DATABASE_URL', '')

    if args.url:
        return args.url

    if args.dev:
        # Replace database name with dev version
        if '/a2a_server' in base_url and '_dev' not in base_url:
            return base_url.replace('/a2a_server', '/a2a_server_dev')
        return base_url

    if args.prod:
        # Ensure we're using prod database (remove _dev suffix if present)
        return base_url.replace('/a2a_server_dev', '/a2a_server')

    # Default: use DATABASE_URL as-is
    return base_url


def main():
    parser = argparse.ArgumentParser(
        description='Run A2A Server database migrations'
    )
    parser.add_argument(
        '--dev',
        action='store_true',
        help='Use development database (a2a_server_dev)',
    )
    parser.add_argument(
        '--prod',
        action='store_true',
        help='Use production database (a2a_server)',
    )
    parser.add_argument('--url', type=str, help='Specific database URL to use')
    parser.add_argument(
        '--create',
        action='store_true',
        help='Create database if it does not exist',
    )
    args = parser.parse_args()

    if args.dev and args.prod:
        print('Error: Cannot specify both --dev and --prod')
        sys.exit(1)

    database_url = get_database_url(args)

    if not database_url:
        print('Error: DATABASE_URL not set. Check your .env file.')
        sys.exit(1)

    # Create database if requested
    if args.create:
        import asyncpg

        # Parse database name from URL
        db_name = database_url.rsplit('/', 1)[-1]
        base_url = database_url.rsplit('/', 1)[0] + '/postgres'

        async def create_db():
            try:
                conn = await asyncpg.connect(base_url)
                # Check if database exists
                exists = await conn.fetchval(
                    'SELECT 1 FROM pg_database WHERE datname = $1', db_name
                )
                if not exists:
                    await conn.execute(f'CREATE DATABASE {db_name}')
                    print(f'Created database: {db_name}')
                else:
                    print(f'Database already exists: {db_name}')
                await conn.close()
            except Exception as e:
                print(f'Failed to create database: {e}')
                sys.exit(1)

        asyncio.run(create_db())

    # Run migrations
    success = asyncio.run(run_migrations(database_url))
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
