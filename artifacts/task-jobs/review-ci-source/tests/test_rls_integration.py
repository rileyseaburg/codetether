"""
Integration tests for PostgreSQL Row-Level Security (RLS).

These tests verify that RLS actually works by:
1. Creating a test table with RLS enabled
2. Inserting data as different tenants
3. Verifying tenant isolation at the database level

IMPORTANT: RLS is bypassed by superusers. These tests use a non-superuser
(a2a_test_user) to verify that RLS actually enforces isolation.

Requirements:
- PostgreSQL database accessible
- a2a_test_user role created (non-superuser)
- pytest-asyncio installed

Run with:
    pytest tests/test_rls_integration.py -v
"""

import os
import uuid
import pytest
from contextlib import asynccontextmanager

# Skip if asyncpg not available
asyncpg = pytest.importorskip('asyncpg')

# Admin URL for setup/teardown (needs superuser for CREATE/DROP)
ADMIN_DATABASE_URL = os.environ.get(
    'DATABASE_URL',
    'postgresql://postgres:spike2@192.168.50.70:5432/a2a_server',
)

# Test user URL - MUST be a non-superuser for RLS to work!
# Superusers bypass RLS even with FORCE ROW LEVEL SECURITY
TEST_DATABASE_URL = os.environ.get(
    'TEST_DATABASE_URL',
    'postgresql://a2a_test_user:testpass123@192.168.50.70:5432/a2a_server',
)


# SQL to create the test table with RLS
CREATE_TEST_TABLE_SQL = """
    DROP TABLE IF EXISTS rls_test_items CASCADE;
    
    CREATE TABLE rls_test_items (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        tenant_id TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    
    -- Create the tenant ID function
    -- IMPORTANT: current_setting returns '' (empty string) not NULL when not set
    -- We must treat both NULL and '' as "no tenant context"
    CREATE OR REPLACE FUNCTION get_current_tenant_id()
    RETURNS TEXT AS $$
    DECLARE
        tenant_id TEXT;
    BEGIN
        tenant_id := current_setting('app.current_tenant_id', true);
        IF tenant_id IS NULL OR tenant_id = '' THEN
            RETURN NULL;
        END IF;
        RETURN tenant_id;
    EXCEPTION
        WHEN OTHERS THEN
            RETURN NULL;
    END;
    $$ LANGUAGE plpgsql STABLE SECURITY DEFINER;
    
    -- Enable RLS
    ALTER TABLE rls_test_items ENABLE ROW LEVEL SECURITY;
    ALTER TABLE rls_test_items FORCE ROW LEVEL SECURITY;
    
    -- Drop existing policies
    DROP POLICY IF EXISTS tenant_select ON rls_test_items;
    DROP POLICY IF EXISTS tenant_insert ON rls_test_items;
    DROP POLICY IF EXISTS tenant_update ON rls_test_items;
    DROP POLICY IF EXISTS tenant_delete ON rls_test_items;
    
    -- SELECT: Only see your tenant's rows (or all if no tenant set)
    CREATE POLICY tenant_select ON rls_test_items
        FOR SELECT
        USING (
            tenant_id = get_current_tenant_id()
            OR get_current_tenant_id() IS NULL
        );
    
    -- INSERT: Can only insert for your tenant
    CREATE POLICY tenant_insert ON rls_test_items
        FOR INSERT
        WITH CHECK (
            tenant_id = get_current_tenant_id()
            OR get_current_tenant_id() IS NULL
        );
    
    -- UPDATE: Can only update your tenant's rows
    CREATE POLICY tenant_update ON rls_test_items
        FOR UPDATE
        USING (tenant_id = get_current_tenant_id() OR get_current_tenant_id() IS NULL)
        WITH CHECK (tenant_id = get_current_tenant_id() OR get_current_tenant_id() IS NULL);
    
    -- DELETE: Can only delete your tenant's rows
    CREATE POLICY tenant_delete ON rls_test_items
        FOR DELETE
        USING (tenant_id = get_current_tenant_id() OR get_current_tenant_id() IS NULL);
    
    -- Grant permissions to test user
    GRANT ALL ON rls_test_items TO a2a_test_user;
"""


@asynccontextmanager
async def rls_test_table():
    """Context manager that creates and cleans up test table."""
    admin_conn = await asyncpg.connect(ADMIN_DATABASE_URL)
    try:
        await admin_conn.execute(CREATE_TEST_TABLE_SQL)
        yield
    finally:
        await admin_conn.execute('DROP TABLE IF EXISTS rls_test_items CASCADE')
        await admin_conn.close()


@asynccontextmanager
async def rls_user_connection():
    """Context manager for non-superuser connection (for RLS testing)."""
    conn = await asyncpg.connect(TEST_DATABASE_URL)
    try:
        yield conn
    finally:
        await conn.execute('RESET app.current_tenant_id')
        await conn.close()


@asynccontextmanager
async def admin_connection():
    """Context manager for admin connection."""
    conn = await asyncpg.connect(ADMIN_DATABASE_URL)
    try:
        yield conn
    finally:
        await conn.close()


class TestRLSIsolation:
    """Test that RLS actually isolates data between tenants."""

    @pytest.mark.asyncio
    async def test_insert_and_read_own_tenant_data(self):
        """Test that a tenant can insert and read their own data."""
        async with rls_test_table():
            async with rls_user_connection() as conn:
                tenant_id = f'tenant-{uuid.uuid4()}'
                item_id = f'item-{uuid.uuid4()}'

                # Set tenant context
                await conn.execute(f"SET app.current_tenant_id = '{tenant_id}'")

                # Insert data
                await conn.execute(
                    'INSERT INTO rls_test_items (id, name, tenant_id) VALUES ($1, $2, $3)',
                    item_id,
                    'Test Item',
                    tenant_id,
                )

                # Read it back
                row = await conn.fetchrow(
                    'SELECT * FROM rls_test_items WHERE id = $1', item_id
                )

                assert row is not None
                assert row['id'] == item_id
                assert row['name'] == 'Test Item'
                assert row['tenant_id'] == tenant_id

    @pytest.mark.asyncio
    async def test_tenant_cannot_see_other_tenant_data(self):
        """Test that tenant A cannot see tenant B's data."""
        async with rls_test_table():
            tenant_a = f'tenant-a-{uuid.uuid4()}'
            tenant_b = f'tenant-b-{uuid.uuid4()}'
            item_a = f'item-a-{uuid.uuid4()}'
            item_b = f'item-b-{uuid.uuid4()}'

            # Insert as admin (no RLS enforcement for superuser)
            async with admin_connection() as admin:
                await admin.execute(
                    'INSERT INTO rls_test_items (id, name, tenant_id) VALUES ($1, $2, $3)',
                    item_a,
                    'Tenant A Item',
                    tenant_a,
                )
                await admin.execute(
                    'INSERT INTO rls_test_items (id, name, tenant_id) VALUES ($1, $2, $3)',
                    item_b,
                    'Tenant B Item',
                    tenant_b,
                )

            # Now test with non-superuser
            async with rls_user_connection() as conn:
                # Set tenant A context
                await conn.execute(f"SET app.current_tenant_id = '{tenant_a}'")

                # Tenant A should see their item
                row_a = await conn.fetchrow(
                    'SELECT * FROM rls_test_items WHERE id = $1', item_a
                )
                assert row_a is not None, 'Tenant A should see their own item'

                # Tenant A should NOT see tenant B's item
                row_b = await conn.fetchrow(
                    'SELECT * FROM rls_test_items WHERE id = $1', item_b
                )
                assert row_b is None, "Tenant A should NOT see tenant B's item"

                # Count - tenant A should only see 1 item
                count = await conn.fetchval(
                    'SELECT COUNT(*) FROM rls_test_items WHERE id IN ($1, $2)',
                    item_a,
                    item_b,
                )
                assert count == 1, (
                    f'Tenant A should only see 1 item, but saw {count}'
                )

    @pytest.mark.asyncio
    async def test_tenant_cannot_update_other_tenant_data(self):
        """Test that tenant A cannot update tenant B's data."""
        async with rls_test_table():
            tenant_a = f'tenant-a-{uuid.uuid4()}'
            tenant_b = f'tenant-b-{uuid.uuid4()}'
            item_b = f'item-b-{uuid.uuid4()}'

            # Insert as admin
            async with admin_connection() as admin:
                await admin.execute(
                    'INSERT INTO rls_test_items (id, name, tenant_id) VALUES ($1, $2, $3)',
                    item_b,
                    'Original Name',
                    tenant_b,
                )

            # Test with non-superuser
            async with rls_user_connection() as conn:
                # Set tenant A context
                await conn.execute(f"SET app.current_tenant_id = '{tenant_a}'")

                # Try to update tenant B's item
                result = await conn.execute(
                    'UPDATE rls_test_items SET name = $1 WHERE id = $2',
                    'Hacked Name',
                    item_b,
                )

                # Should not have updated any rows (RLS blocked it)
                assert result == 'UPDATE 0', (
                    f'Update should have affected 0 rows, got: {result}'
                )

            # Verify original data unchanged (check as admin)
            async with admin_connection() as admin:
                row = await admin.fetchrow(
                    'SELECT * FROM rls_test_items WHERE id = $1', item_b
                )
                assert row['name'] == 'Original Name', (
                    'Data should not have been modified'
                )

    @pytest.mark.asyncio
    async def test_tenant_cannot_delete_other_tenant_data(self):
        """Test that tenant A cannot delete tenant B's data."""
        async with rls_test_table():
            tenant_a = f'tenant-a-{uuid.uuid4()}'
            tenant_b = f'tenant-b-{uuid.uuid4()}'
            item_b = f'item-b-{uuid.uuid4()}'

            # Insert as admin
            async with admin_connection() as admin:
                await admin.execute(
                    'INSERT INTO rls_test_items (id, name, tenant_id) VALUES ($1, $2, $3)',
                    item_b,
                    'Tenant B Item',
                    tenant_b,
                )

            # Test with non-superuser
            async with rls_user_connection() as conn:
                # Set tenant A context
                await conn.execute(f"SET app.current_tenant_id = '{tenant_a}'")

                # Try to delete tenant B's item
                result = await conn.execute(
                    'DELETE FROM rls_test_items WHERE id = $1', item_b
                )

                # Should not have deleted any rows
                assert result == 'DELETE 0', (
                    f'Delete should have affected 0 rows, got: {result}'
                )

            # Verify data still exists (check as admin)
            async with admin_connection() as admin:
                row = await admin.fetchrow(
                    'SELECT * FROM rls_test_items WHERE id = $1', item_b
                )
                assert row is not None, 'Data should still exist'

    @pytest.mark.asyncio
    async def test_no_tenant_context_sees_all_data(self):
        """Test that without tenant context, all data is visible (admin mode)."""
        async with rls_test_table():
            tenant_a = f'tenant-a-{uuid.uuid4()}'
            tenant_b = f'tenant-b-{uuid.uuid4()}'
            item_a = f'item-a-{uuid.uuid4()}'
            item_b = f'item-b-{uuid.uuid4()}'

            # Insert data as admin
            async with admin_connection() as admin:
                await admin.execute(
                    'INSERT INTO rls_test_items (id, name, tenant_id) VALUES ($1, $2, $3)',
                    item_a,
                    'Tenant A Item',
                    tenant_a,
                )
                await admin.execute(
                    'INSERT INTO rls_test_items (id, name, tenant_id) VALUES ($1, $2, $3)',
                    item_b,
                    'Tenant B Item',
                    tenant_b,
                )

            # Test user with no tenant context should see all
            async with rls_user_connection() as conn:
                # No tenant context set - get_current_tenant_id() returns NULL
                # Policy allows access when tenant context is NULL
                count = await conn.fetchval(
                    'SELECT COUNT(*) FROM rls_test_items WHERE id IN ($1, $2)',
                    item_a,
                    item_b,
                )
                assert count == 2, (
                    f'No tenant context should see all 2 items, but saw {count}'
                )

    @pytest.mark.asyncio
    async def test_switching_tenant_context(self):
        """Test that switching tenant context changes what data is visible."""
        async with rls_test_table():
            tenant_a = f'tenant-a-{uuid.uuid4()}'
            tenant_b = f'tenant-b-{uuid.uuid4()}'
            item_a = f'item-a-{uuid.uuid4()}'
            item_b = f'item-b-{uuid.uuid4()}'

            # Insert data as admin
            async with admin_connection() as admin:
                await admin.execute(
                    'INSERT INTO rls_test_items (id, name, tenant_id) VALUES ($1, $2, $3)',
                    item_a,
                    'Tenant A Item',
                    tenant_a,
                )
                await admin.execute(
                    'INSERT INTO rls_test_items (id, name, tenant_id) VALUES ($1, $2, $3)',
                    item_b,
                    'Tenant B Item',
                    tenant_b,
                )

            async with rls_user_connection() as conn:
                # As tenant A
                await conn.execute(f"SET app.current_tenant_id = '{tenant_a}'")
                rows_a = await conn.fetch(
                    'SELECT id FROM rls_test_items WHERE id IN ($1, $2)',
                    item_a,
                    item_b,
                )
                assert len(rows_a) == 1, (
                    f'Tenant A should see 1 item, saw {len(rows_a)}'
                )
                assert rows_a[0]['id'] == item_a

                # Switch to tenant B
                await conn.execute(f"SET app.current_tenant_id = '{tenant_b}'")
                rows_b = await conn.fetch(
                    'SELECT id FROM rls_test_items WHERE id IN ($1, $2)',
                    item_a,
                    item_b,
                )
                assert len(rows_b) == 1, (
                    f'Tenant B should see 1 item, saw {len(rows_b)}'
                )
                assert rows_b[0]['id'] == item_b


class TestRLSInsertRestrictions:
    """Test that RLS prevents inserting data for wrong tenants."""

    @pytest.mark.asyncio
    async def test_cannot_insert_for_different_tenant(self):
        """Test that tenant A cannot insert data claiming to be tenant B."""
        async with rls_test_table():
            tenant_a = f'tenant-a-{uuid.uuid4()}'
            tenant_b = f'tenant-b-{uuid.uuid4()}'
            item_id = f'item-{uuid.uuid4()}'

            async with rls_user_connection() as conn:
                # Set tenant A context
                await conn.execute(f"SET app.current_tenant_id = '{tenant_a}'")

                # Try to insert data for tenant B - should fail
                insert_succeeded = False
                try:
                    await conn.execute(
                        'INSERT INTO rls_test_items (id, name, tenant_id) VALUES ($1, $2, $3)',
                        item_id,
                        'Malicious Item',
                        tenant_b,
                    )
                    insert_succeeded = True
                except asyncpg.exceptions.InsufficientPrivilegeError:
                    # Expected - RLS blocked the insert
                    pass
                except Exception as e:
                    if 'policy' in str(e).lower() or 'rls' in str(e).lower():
                        pass  # RLS blocked it
                    else:
                        raise

                # If insert appeared to succeed, verify it was actually blocked
                if insert_succeeded:
                    # Check as admin if data was inserted
                    async with admin_connection() as admin:
                        row = await admin.fetchrow(
                            'SELECT * FROM rls_test_items WHERE id = $1',
                            item_id,
                        )
                        if row is not None:
                            pytest.fail(
                                'RLS should have blocked insert for different tenant'
                            )


class TestRLSContextManagement:
    """Test tenant context management functions."""

    @pytest.mark.asyncio
    async def test_get_current_tenant_id_returns_null_when_not_set(self):
        """Test that get_current_tenant_id() returns NULL when not set."""
        async with rls_test_table():
            async with rls_user_connection() as conn:
                result = await conn.fetchval('SELECT get_current_tenant_id()')
                assert result is None, f'Expected NULL but got: {repr(result)}'

    @pytest.mark.asyncio
    async def test_get_current_tenant_id_returns_value_when_set(self):
        """Test that get_current_tenant_id() returns the set value."""
        async with rls_test_table():
            async with rls_user_connection() as conn:
                tenant_id = f'tenant-{uuid.uuid4()}'

                await conn.execute(f"SET app.current_tenant_id = '{tenant_id}'")
                result = await conn.fetchval('SELECT get_current_tenant_id()')
                assert result == tenant_id

    @pytest.mark.asyncio
    async def test_reset_clears_tenant_context(self):
        """Test that RESET clears the tenant context."""
        async with rls_test_table():
            async with rls_user_connection() as conn:
                tenant_id = f'tenant-{uuid.uuid4()}'

                await conn.execute(f"SET app.current_tenant_id = '{tenant_id}'")
                result_before = await conn.fetchval(
                    'SELECT get_current_tenant_id()'
                )
                assert result_before == tenant_id

                await conn.execute('RESET app.current_tenant_id')
                result_after = await conn.fetchval(
                    'SELECT get_current_tenant_id()'
                )
                assert result_after is None, (
                    f'Expected NULL after reset but got: {repr(result_after)}'
                )
