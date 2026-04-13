from .database import get_pool
from .user_auth import hash_password


async def ensure_external_user_profile(
    user_id: str,
    email: str,
    name: str,
    tenant_id: str | None,
) -> None:
    pool = await get_pool()
    if not pool:
        return
    parts = [part for part in name.split() if part]
    first_name = parts[0] if parts else None
    last_name = ' '.join(parts[1:]) if len(parts) > 1 else None
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users (
                id, email, password_hash, first_name, last_name,
                status, email_verified, tenant_id, tasks_limit
            ) VALUES ($1, $2, $3, $4, $5, 'active', TRUE, $6, 10)
            ON CONFLICT (id) DO UPDATE SET
                email = EXCLUDED.email,
                first_name = COALESCE(users.first_name, EXCLUDED.first_name),
                last_name = COALESCE(users.last_name, EXCLUDED.last_name),
                tenant_id = COALESCE(users.tenant_id, EXCLUDED.tenant_id),
                status = 'active',
                email_verified = TRUE,
                updated_at = NOW()
            """,
            user_id,
            email.lower(),
            hash_password(f'keycloak:{user_id}'),
            first_name,
            last_name,
            tenant_id,
        )
