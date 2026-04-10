"""
Admin Dashboard API for A2A Server.

Provides bird's eye view for administrators:
- User and tenant statistics
- Subscription/billing overview
- Kubernetes instance health
- System metrics and alerts

All endpoints require Keycloak admin role authorization.
Users must have 'admin' or 'a2a-admin' role in their Keycloak realm.
"""

import logging
import os
import json
import re
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from .database import RLS_ENABLED as DB_RLS_ENABLED, get_pool, get_tenant_by_realm, tenant_scope
from .keycloak_auth import require_admin, UserSession, KEYCLOAK_REALM
from .policy import (
    OPA_LOCAL_MODE,
    POLICIES_DIR,
    reload_local_policy_data,
    require_permission,
)
from .tenant_service import KeycloakTenantService, KeycloakTenantServiceError

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/v1/admin', tags=['Admin'])


# ========================================
# Response Models
# ========================================


class UserStats(BaseModel):
    """User statistics."""

    total_users: int
    active_users: int
    users_last_24h: int
    users_last_7d: int
    users_last_30d: int
    pending_verification: int
    suspended: int


class TenantStats(BaseModel):
    """Tenant statistics."""

    total_tenants: int
    tenants_by_plan: Dict[str, int]
    tenants_with_k8s: int
    tenants_last_24h: int
    tenants_last_7d: int


class SubscriptionStats(BaseModel):
    """Subscription/billing statistics."""

    total_subscriptions: int
    active_subscriptions: int
    mrr_estimate: float  # Monthly recurring revenue
    subscriptions_by_tier: Dict[str, int]
    past_due: int
    canceled_last_30d: int


class K8sInstanceSummary(BaseModel):
    """Summary of a K8s instance."""

    namespace: str
    tenant_id: str
    tenant_name: str
    user_email: str
    tier: str
    status: str  # running, suspended, unknown
    pods_ready: int
    pods_total: int
    external_url: Optional[str]
    created_at: Optional[str]


class K8sClusterStats(BaseModel):
    """Kubernetes cluster statistics."""

    total_namespaces: int
    running_instances: int
    suspended_instances: int
    total_pods: int
    healthy_pods: int
    unhealthy_pods: int
    instances: List[K8sInstanceSummary]


class SystemHealth(BaseModel):
    """System health overview."""

    database: str  # healthy, degraded, down
    keycloak: str
    kubernetes: str
    stripe: str
    redis: str


class AlertItem(BaseModel):
    """System alert."""

    level: str  # info, warning, critical
    message: str
    timestamp: str
    source: str


class AdminDashboard(BaseModel):
    """Complete admin dashboard response."""

    generated_at: str
    users: UserStats
    tenants: TenantStats
    subscriptions: SubscriptionStats
    k8s_cluster: Optional[K8sClusterStats]
    system_health: SystemHealth
    alerts: List[AlertItem]
    recent_signups: List[Dict[str, Any]]
    recent_tasks: Dict[str, int]


class PolicyRoleDefinition(BaseModel):
    """Role definition stored in policies/data.json."""

    description: str = ''
    permissions: List[str] = []
    inherits: Optional[str] = None


class PolicyRBACResponse(BaseModel):
    """RBAC policy payload for admin UI."""

    roles: Dict[str, PolicyRoleDefinition]
    permissions: List[str]
    permissions_by_resource: Dict[str, List[str]]
    metadata: Dict[str, Any]


class UpdatePolicyRoleRequest(BaseModel):
    """Create/update request for a policy role."""

    description: str = ''
    permissions: List[str] = []
    inherits: Optional[str] = None


class UpdatePolicyRoleResponse(BaseModel):
    """Create/update response for a policy role."""

    role_name: str
    role: PolicyRoleDefinition
    metadata: Dict[str, Any]


class RBACRoleCatalogResponse(BaseModel):
    """Role catalog for Keycloak + OPA management."""

    realm_name: str
    opa_roles: List[str]
    keycloak_roles: List[str]
    missing_in_keycloak: List[str]
    metadata: Dict[str, Any]


class RBACSyncRolesResponse(BaseModel):
    """Result of syncing OPA roles to Keycloak realm roles."""

    realm_name: str
    created: List[str]
    existing: List[str]
    failed: Dict[str, str]


class RBACUserSummary(BaseModel):
    """User row in RBAC user management list."""

    id: str
    email: str
    username: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    name: Optional[str] = None
    enabled: bool = True
    email_verified: bool = False
    roles: List[str] = []
    opa_roles: List[str] = []
    db_opa_roles: List[str] = []
    db_synced: Optional[bool] = None


class RBACUserListResponse(BaseModel):
    """Response model for RBAC user listing."""

    realm_name: str
    users: List[RBACUserSummary]
    total: int
    limit: int
    offset: int
    metadata: Dict[str, Any]


class RBACUserRoleUpdateRequest(BaseModel):
    """Request model to update OPA-managed Keycloak roles for one user."""

    roles: List[str]
    realm_name: Optional[str] = None
    sync_missing_roles: bool = True


class RBACUserRoleUpdateResponse(BaseModel):
    """Response model for user role updates."""

    realm_name: str
    user_id: str
    assigned: List[str]
    removed: List[str]
    roles: List[str]
    tenant_id: Optional[str] = None
    postgres_synced: bool = False
    metadata: Dict[str, Any]


# Shared validation patterns for RBAC role edits.
_ROLE_NAME_RE = re.compile(r'^[a-z0-9][a-z0-9_-]{1,63}$')
_PERMISSION_RE = re.compile(r'^[a-z_][a-z0-9_]*:[a-z*][a-z0-9_*-]*$')


# ========================================
# Data Fetching Functions
# ========================================


def _policy_data_file() -> Path:
    return POLICIES_DIR / 'data.json'


def _opa_role_names() -> List[str]:
    data = _load_policy_data_or_error()
    roles = data.get('roles', {})
    if not isinstance(roles, dict):
        return []
    return sorted(
        role_name
        for role_name in roles.keys()
        if isinstance(role_name, str) and role_name.strip()
    )


def _resolve_realm_name(
    admin: UserSession, explicit_realm_name: Optional[str] = None
) -> str:
    if explicit_realm_name and explicit_realm_name.strip():
        return explicit_realm_name.strip()
    if admin.realm_name:
        return admin.realm_name
    return KEYCLOAK_REALM


async def _resolve_tenant_id_for_realm(
    admin: UserSession, realm_name: str
) -> Optional[str]:
    if admin.tenant_id and (
        not admin.realm_name or admin.realm_name == realm_name
    ):
        return admin.tenant_id

    tenant = await get_tenant_by_realm(realm_name)
    if tenant and tenant.get('id'):
        return str(tenant['id'])
    return None


async def _fetch_postgres_rbac_roles(
    tenant_id: Optional[str], user_ids: List[str]
) -> Dict[str, List[str]]:
    if not tenant_id or not user_ids:
        return {}

    try:
        async with tenant_scope(tenant_id) as conn:
            rows = await conn.fetch(
                """
                SELECT user_id, roles
                FROM rbac_user_roles
                WHERE tenant_id = $1
                  AND user_id = ANY($2::TEXT[])
                """,
                tenant_id,
                user_ids,
            )
    except Exception as e:
        logger.warning(f'Failed to fetch Postgres RBAC role snapshots: {e}')
        return {}

    role_map: Dict[str, List[str]] = {}
    for row in rows:
        roles = row['roles'] or []
        role_map[str(row['user_id'])] = sorted(
            {
                role.strip()
                for role in roles
                if isinstance(role, str) and role.strip()
            }
        )
    return role_map


async def _upsert_postgres_rbac_roles(
    tenant_id: Optional[str],
    realm_name: str,
    entries: List[Dict[str, Any]],
    updated_by: str,
) -> bool:
    if not tenant_id or not entries:
        return False

    values = []
    for entry in entries:
        roles = entry.get('roles') or []
        normalized_roles = sorted(
            {
                role.strip()
                for role in roles
                if isinstance(role, str) and role.strip()
            }
        )
        values.append(
            (
                tenant_id,
                realm_name,
                str(entry.get('user_id') or ''),
                str(entry.get('email') or ''),
                normalized_roles,
                str(entry.get('source') or 'keycloak_sync'),
                updated_by,
            )
        )

    if not values:
        return False

    try:
        async with tenant_scope(tenant_id) as conn:
            await conn.executemany(
                """
                INSERT INTO rbac_user_roles (
                    tenant_id, realm_name, user_id, email, roles, source, updated_by
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (tenant_id, user_id) DO UPDATE SET
                    realm_name = EXCLUDED.realm_name,
                    email = CASE
                        WHEN EXCLUDED.email = '' THEN rbac_user_roles.email
                        ELSE EXCLUDED.email
                    END,
                    roles = EXCLUDED.roles,
                    source = EXCLUDED.source,
                    updated_by = EXCLUDED.updated_by,
                    updated_at = NOW()
                """,
                values,
            )
        return True
    except Exception as e:
        logger.warning(f'Failed to upsert Postgres RBAC role snapshots: {e}')
        return False


def _policy_metadata(policy_file: Path) -> Dict[str, Any]:
    mtime = None
    if policy_file.exists():
        mtime = datetime.utcfromtimestamp(
            policy_file.stat().st_mtime
        ).isoformat()

    return {
        'opa_local_mode': OPA_LOCAL_MODE,
        'changes_apply_immediately': OPA_LOCAL_MODE,
        'reload_required': not OPA_LOCAL_MODE,
        'data_file': str(policy_file),
        'writable': os.access(policy_file.parent, os.W_OK),
        'updated_at': mtime,
    }


def _load_policy_data_or_error() -> Dict[str, Any]:
    policy_file = _policy_data_file()
    if not policy_file.exists():
        raise HTTPException(
            status_code=500,
            detail=f'Policy data file not found: {policy_file}',
        )

    try:
        with open(policy_file, encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=500,
            detail=f'Invalid JSON in policy data file: {e}',
        ) from e
    except OSError as e:
        raise HTTPException(
            status_code=500,
            detail=f'Failed to read policy data file: {e}',
        ) from e

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=500, detail='Policy data file must contain a JSON object'
        )

    roles = data.setdefault('roles', {})
    if not isinstance(roles, dict):
        raise HTTPException(
            status_code=500,
            detail="Policy data file key 'roles' must be an object",
        )

    return data


def _write_policy_data_or_error(data: Dict[str, Any]) -> None:
    policy_file = _policy_data_file()
    policy_file.parent.mkdir(parents=True, exist_ok=True)

    payload = json.dumps(data, indent=4) + '\n'
    fd, tmp_path = tempfile.mkstemp(
        prefix='policy-data-', suffix='.json', dir=str(policy_file.parent)
    )

    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as tmp_file:
            tmp_file.write(payload)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
        os.replace(tmp_path, policy_file)
    except OSError as e:
        raise HTTPException(
            status_code=500,
            detail=f'Failed to persist policy data: {e}',
        ) from e
    finally:
        if os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def _build_permission_catalog(
    roles: Dict[str, Any],
) -> tuple[List[str], Dict[str, List[str]]]:
    permissions: set[str] = set()

    for role in roles.values():
        if not isinstance(role, dict):
            continue
        for permission in role.get('permissions', []):
            if isinstance(permission, str) and ':' in permission:
                permissions.add(permission)

    permission_list = sorted(permissions)
    grouped: Dict[str, List[str]] = {}
    for permission in permission_list:
        resource = permission.split(':', 1)[0]
        grouped.setdefault(resource, []).append(permission)

    return permission_list, grouped


def _normalize_role(
    role_name: str,
    request: UpdatePolicyRoleRequest,
    existing_roles: Dict[str, Any],
) -> PolicyRoleDefinition:
    if not _ROLE_NAME_RE.match(role_name):
        raise HTTPException(
            status_code=400,
            detail='Role name must be 2-64 chars: lowercase letters, numbers, "_" or "-"',
        )

    description = request.description.strip()
    inherits = request.inherits.strip() if request.inherits else None

    permissions = sorted(
        {
            permission.strip()
            for permission in request.permissions
            if isinstance(permission, str) and permission.strip()
        }
    )

    if inherits:
        if inherits == role_name:
            raise HTTPException(
                status_code=400, detail='A role cannot inherit from itself'
            )
        if inherits not in existing_roles:
            raise HTTPException(
                status_code=400,
                detail=f"Inherited role '{inherits}' does not exist",
            )
        if permissions:
            raise HTTPException(
                status_code=400,
                detail='Inherited roles cannot also define explicit permissions',
            )
        return PolicyRoleDefinition(
            description=description,
            permissions=[],
            inherits=inherits,
        )

    if not permissions:
        raise HTTPException(
            status_code=400,
            detail='Custom roles must include at least one permission',
        )

    invalid_permissions = [
        permission
        for permission in permissions
        if not _PERMISSION_RE.match(permission)
    ]
    if invalid_permissions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid permission format: '{invalid_permissions[0]}'",
        )

    return PolicyRoleDefinition(
        description=description,
        permissions=permissions,
        inherits=None,
    )


async def get_user_stats() -> UserStats:
    """Get user statistics from database."""
    pool = await get_pool()
    if not pool:
        return UserStats(
            total_users=0,
            active_users=0,
            users_last_24h=0,
            users_last_7d=0,
            users_last_30d=0,
            pending_verification=0,
            suspended=0,
        )

    async with pool.acquire() as conn:
        # Total users
        total = await conn.fetchval('SELECT COUNT(*) FROM users')

        # Active users
        active = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE status = 'active'"
        )

        # Users by time period
        now = datetime.utcnow()
        last_24h = await conn.fetchval(
            'SELECT COUNT(*) FROM users WHERE created_at > $1',
            now - timedelta(hours=24),
        )
        last_7d = await conn.fetchval(
            'SELECT COUNT(*) FROM users WHERE created_at > $1',
            now - timedelta(days=7),
        )
        last_30d = await conn.fetchval(
            'SELECT COUNT(*) FROM users WHERE created_at > $1',
            now - timedelta(days=30),
        )

        # By status
        pending = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE status = 'pending_verification'"
        )
        suspended = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE status = 'suspended'"
        )

        return UserStats(
            total_users=total or 0,
            active_users=active or 0,
            users_last_24h=last_24h or 0,
            users_last_7d=last_7d or 0,
            users_last_30d=last_30d or 0,
            pending_verification=pending or 0,
            suspended=suspended or 0,
        )


async def get_tenant_stats() -> TenantStats:
    """Get tenant statistics from database."""
    pool = await get_pool()
    if not pool:
        return TenantStats(
            total_tenants=0,
            tenants_by_plan={},
            tenants_with_k8s=0,
            tenants_last_24h=0,
            tenants_last_7d=0,
        )

    async with pool.acquire() as conn:
        # Total tenants
        total = await conn.fetchval('SELECT COUNT(*) FROM tenants')

        # By plan
        plan_rows = await conn.fetch(
            'SELECT plan, COUNT(*) as count FROM tenants GROUP BY plan'
        )
        by_plan = {row['plan']: row['count'] for row in plan_rows}

        # With K8s
        with_k8s = await conn.fetchval(
            'SELECT COUNT(*) FROM tenants WHERE k8s_namespace IS NOT NULL'
        )

        # By time
        now = datetime.utcnow()
        last_24h = await conn.fetchval(
            'SELECT COUNT(*) FROM tenants WHERE created_at > $1',
            now - timedelta(hours=24),
        )
        last_7d = await conn.fetchval(
            'SELECT COUNT(*) FROM tenants WHERE created_at > $1',
            now - timedelta(days=7),
        )

        return TenantStats(
            total_tenants=total or 0,
            tenants_by_plan=by_plan,
            tenants_with_k8s=with_k8s or 0,
            tenants_last_24h=last_24h or 0,
            tenants_last_7d=last_7d or 0,
        )


async def get_subscription_stats() -> SubscriptionStats:
    """Get subscription/billing statistics."""
    pool = await get_pool()
    if not pool:
        return SubscriptionStats(
            total_subscriptions=0,
            active_subscriptions=0,
            mrr_estimate=0.0,
            subscriptions_by_tier={},
            past_due=0,
            canceled_last_30d=0,
        )

    # Tier pricing for MRR calculation
    tier_prices = {
        'free': 0,
        'pro': 297,
        'agency': 497,
        'enterprise': 997,
    }

    async with pool.acquire() as conn:
        # From users table (mid-market)
        user_tiers = await conn.fetch("""
            SELECT tier_id, COUNT(*) as count 
            FROM users 
            WHERE tier_id IS NOT NULL 
            GROUP BY tier_id
        """)

        # From tenants table (B2B)
        tenant_plans = await conn.fetch("""
            SELECT plan, COUNT(*) as count,
                   SUM(CASE WHEN stripe_subscription_id IS NOT NULL 
                       AND stripe_subscription_id != '' THEN 1 ELSE 0 END) as with_subscription
            FROM tenants 
            GROUP BY plan
        """)

        # Calculate totals
        by_tier = {}
        total_active = 0
        mrr = 0.0

        for row in user_tiers:
            tier = row['tier_id'] or 'free'
            count = row['count']
            by_tier[tier] = by_tier.get(tier, 0) + count
            if tier != 'free':
                total_active += count
                mrr += count * tier_prices.get(tier, 0)

        for row in tenant_plans:
            plan = row['plan'] or 'free'
            count = row['count']
            by_tier[plan] = by_tier.get(plan, 0) + count
            if plan != 'free' and row['with_subscription']:
                total_active += row['with_subscription']
                mrr += row['with_subscription'] * tier_prices.get(plan, 0)

        # Past due (users)
        past_due = await conn.fetchval("""
            SELECT COUNT(*) FROM users 
            WHERE stripe_subscription_status = 'past_due'
        """)

        # Canceled last 30 days
        now = datetime.utcnow()
        canceled = await conn.fetchval(
            """
            SELECT COUNT(*) FROM users 
            WHERE stripe_subscription_status = 'canceled'
            AND updated_at > $1
        """,
            now - timedelta(days=30),
        )

        return SubscriptionStats(
            total_subscriptions=sum(by_tier.values()),
            active_subscriptions=total_active,
            mrr_estimate=mrr,
            subscriptions_by_tier=by_tier,
            past_due=past_due or 0,
            canceled_last_30d=canceled or 0,
        )


async def get_k8s_cluster_stats() -> Optional[K8sClusterStats]:
    """Get Kubernetes cluster statistics."""
    try:
        from .k8s_provisioning import k8s_provisioning_service, K8S_AVAILABLE

        if not K8S_AVAILABLE:
            return None

        if not k8s_provisioning_service._init_k8s_client():
            return None

        # Get all tenant namespaces from database
        pool = await get_pool()
        if not pool:
            return None

        instances = []
        total_pods = 0
        healthy_pods = 0
        running = 0
        suspended = 0

        async with pool.acquire() as conn:
            tenants = await conn.fetch("""
                SELECT t.id, t.display_name, t.plan, t.k8s_namespace, 
                       t.k8s_external_url, t.created_at,
                       u.email as user_email
                FROM tenants t
                LEFT JOIN users u ON u.tenant_id = t.id
                WHERE t.k8s_namespace IS NOT NULL
            """)

            for tenant in tenants:
                namespace = tenant['k8s_namespace']

                # Get K8s status
                try:
                    status = await k8s_provisioning_service.get_instance_status(
                        namespace
                    )

                    if status:
                        pods = status.get('pods', [])
                        pods_ready = sum(1 for p in pods if p.get('ready'))
                        pods_total = len(pods)

                        total_pods += pods_total
                        healthy_pods += pods_ready

                        instance_status = (
                            'running' if pods_ready > 0 else 'suspended'
                        )
                        if pods_ready > 0:
                            running += 1
                        else:
                            suspended += 1
                    else:
                        pods_ready = 0
                        pods_total = 0
                        instance_status = 'unknown'

                except Exception as e:
                    logger.warning(
                        f'Failed to get K8s status for {namespace}: {e}'
                    )
                    pods_ready = 0
                    pods_total = 0
                    instance_status = 'unknown'

                instances.append(
                    K8sInstanceSummary(
                        namespace=namespace,
                        tenant_id=tenant['id'],
                        tenant_name=tenant['display_name'] or 'Unknown',
                        user_email=tenant['user_email'] or 'Unknown',
                        tier=tenant['plan'] or 'free',
                        status=instance_status,
                        pods_ready=pods_ready,
                        pods_total=pods_total,
                        external_url=tenant['k8s_external_url'],
                        created_at=tenant['created_at'].isoformat()
                        if tenant['created_at']
                        else None,
                    )
                )

        return K8sClusterStats(
            total_namespaces=len(instances),
            running_instances=running,
            suspended_instances=suspended,
            total_pods=total_pods,
            healthy_pods=healthy_pods,
            unhealthy_pods=total_pods - healthy_pods,
            instances=instances,
        )

    except ImportError:
        return None
    except Exception as e:
        logger.error(f'Failed to get K8s stats: {e}')
        return None


async def get_system_health() -> SystemHealth:
    """Check health of all system components."""
    health = {
        'database': 'unknown',
        'keycloak': 'unknown',
        'kubernetes': 'unknown',
        'stripe': 'unknown',
        'redis': 'unknown',
    }

    # Database check
    try:
        pool = await get_pool()
        if pool:
            async with pool.acquire() as conn:
                await conn.fetchval('SELECT 1')
            health['database'] = 'healthy'
        else:
            health['database'] = 'down'
    except Exception as e:
        logger.error(f'Database health check failed: {e}')
        health['database'] = 'down'

    # Keycloak check
    try:
        from .tenant_service import KeycloakTenantService

        service = KeycloakTenantService()
        # Just check if we can get admin token
        await service._get_admin_token()
        health['keycloak'] = 'healthy'
    except Exception as e:
        logger.warning(f'Keycloak health check failed: {e}')
        health['keycloak'] = 'degraded'

    # Kubernetes check
    try:
        from .k8s_provisioning import k8s_provisioning_service, K8S_AVAILABLE

        if K8S_AVAILABLE and k8s_provisioning_service._init_k8s_client():
            health['kubernetes'] = 'healthy'
        else:
            health['kubernetes'] = 'disabled'
    except Exception as e:
        logger.warning(f'K8s health check failed: {e}')
        health['kubernetes'] = 'down'

    # Stripe check
    try:
        import stripe

        if stripe.api_key:
            # Quick API check
            stripe.Account.retrieve()
            health['stripe'] = 'healthy'
        else:
            health['stripe'] = 'not_configured'
    except Exception as e:
        logger.warning(f'Stripe health check failed: {e}')
        health['stripe'] = 'degraded'

    # Redis check
    try:
        import redis

        redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
        r = redis.from_url(redis_url)
        r.ping()
        health['redis'] = 'healthy'
    except Exception as e:
        logger.warning(f'Redis health check failed: {e}')
        health['redis'] = 'down'

    return SystemHealth(**health)


async def get_alerts() -> List[AlertItem]:
    """Get current system alerts."""
    alerts = []
    now = datetime.utcnow()

    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            # Check for past due subscriptions
            past_due = await conn.fetchval(
                "SELECT COUNT(*) FROM users WHERE stripe_subscription_status = 'past_due'"
            )
            if past_due and past_due > 0:
                alerts.append(
                    AlertItem(
                        level='warning',
                        message=f'{past_due} users have past due subscriptions',
                        timestamp=now.isoformat(),
                        source='billing',
                    )
                )

            # Check for failed tasks in last hour
            failed_tasks = await conn.fetchval(
                """
                SELECT COUNT(*) FROM tasks 
                WHERE status = 'failed' 
                AND updated_at > $1
            """,
                now - timedelta(hours=1),
            )
            if failed_tasks and failed_tasks > 10:
                alerts.append(
                    AlertItem(
                        level='warning',
                        message=f'{failed_tasks} tasks failed in the last hour',
                        timestamp=now.isoformat(),
                        source='tasks',
                    )
                )

            # Check for users without tenant
            orphan_users = await conn.fetchval(
                "SELECT COUNT(*) FROM users WHERE tenant_id IS NULL AND status = 'active'"
            )
            if orphan_users and orphan_users > 0:
                alerts.append(
                    AlertItem(
                        level='info',
                        message=f'{orphan_users} active users without tenant assignment',
                        timestamp=now.isoformat(),
                        source='provisioning',
                    )
                )

    return alerts


async def get_recent_signups(limit: int = 10) -> List[Dict[str, Any]]:
    """Get recent user signups."""
    pool = await get_pool()
    if not pool:
        return []

    async with pool.acquire() as conn:
        # Check if k8s_namespace column exists
        try:
            col_check = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'tenants' AND column_name = 'k8s_namespace'
                )
                """
            )
            has_k8s_col = col_check
        except Exception:
            has_k8s_col = False

        if has_k8s_col:
            rows = await conn.fetch(
                """
                SELECT u.id, u.email, u.first_name, u.last_name, u.status,
                       u.created_at, u.tier_id, t.display_name as tenant_name,
                       t.k8s_namespace
                FROM users u
                LEFT JOIN tenants t ON u.tenant_id = t.id
                ORDER BY u.created_at DESC
                LIMIT $1
            """,
                limit,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT u.id, u.email, u.first_name, u.last_name, u.status,
                       u.created_at, u.tier_id, t.display_name as tenant_name,
                       NULL as k8s_namespace
                FROM users u
                LEFT JOIN tenants t ON u.tenant_id = t.id
                ORDER BY u.created_at DESC
                LIMIT $1
            """,
                limit,
            )

        return [
            {
                'id': row['id'],
                'email': row['email'],
                'name': f'{row["first_name"] or ""} {row["last_name"] or ""}'.strip()
                or 'Unknown',
                'status': row['status'],
                'tier': row['tier_id'] or 'free',
                'tenant': row['tenant_name'],
                'has_k8s': bool(row['k8s_namespace'])
                if row['k8s_namespace']
                else False,
                'created_at': row['created_at'].isoformat()
                if row['created_at']
                else None,
            }
            for row in rows
        ]


async def get_task_stats() -> Dict[str, int]:
    """Get task statistics."""
    pool = await get_pool()
    if not pool:
        return {}

    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT status, COUNT(*) as count
            FROM tasks
            WHERE created_at > NOW() - INTERVAL '24 hours'
            GROUP BY status
        """)

        return {row['status']: row['count'] for row in rows}


# ========================================
# API Endpoints
# ========================================


@router.get('/dashboard', response_model=AdminDashboard)
async def get_admin_dashboard(admin: UserSession = Depends(require_admin)):
    """
    Get complete admin dashboard with bird's eye view of the system.

    Requires Keycloak 'admin' or 'a2a-admin' role.

    Returns:
    - User statistics (total, active, by period)
    - Tenant statistics (total, by plan, with K8s)
    - Subscription/billing metrics (MRR, by tier, past due)
    - Kubernetes cluster overview (pods, instances, health)
    - System health status (database, keycloak, k8s, stripe, redis)
    - Active alerts
    - Recent signups
    - Task statistics
    """
    logger.info(f'Admin dashboard accessed by {admin.email}')

    # Fetch all data concurrently
    import asyncio

    (
        user_stats,
        tenant_stats,
        subscription_stats,
        k8s_stats,
        system_health,
        alerts,
        recent_signups,
        task_stats,
    ) = await asyncio.gather(
        get_user_stats(),
        get_tenant_stats(),
        get_subscription_stats(),
        get_k8s_cluster_stats(),
        get_system_health(),
        get_alerts(),
        get_recent_signups(),
        get_task_stats(),
    )

    return AdminDashboard(
        generated_at=datetime.utcnow().isoformat(),
        users=user_stats,
        tenants=tenant_stats,
        subscriptions=subscription_stats,
        k8s_cluster=k8s_stats,
        system_health=system_health,
        alerts=alerts,
        recent_signups=recent_signups,
        recent_tasks=task_stats,
    )


@router.get('/users')
async def list_users(
    status: Optional[str] = None,
    tier: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    admin: UserSession = Depends(require_admin),
):
    """List all users with filtering."""
    pool = await get_pool()
    if not pool:
        raise HTTPException(status_code=503, detail='Database unavailable')

    async with pool.acquire() as conn:
        query = """
            SELECT u.*, t.display_name as tenant_name, t.k8s_namespace,
                   t.k8s_external_url
            FROM users u
            LEFT JOIN tenants t ON u.tenant_id = t.id
            WHERE 1=1
        """
        params = []
        param_idx = 1

        if status:
            query += f' AND u.status = ${param_idx}'
            params.append(status)
            param_idx += 1

        if tier:
            query += f' AND u.tier_id = ${param_idx}'
            params.append(tier)
            param_idx += 1

        query += f' ORDER BY u.created_at DESC LIMIT ${param_idx} OFFSET ${param_idx + 1}'
        params.extend([limit, offset])

        rows = await conn.fetch(query, *params)

        # Get total count
        count_query = 'SELECT COUNT(*) FROM users WHERE 1=1'
        if status:
            count_query += f' AND status = $1'
        total = await conn.fetchval(count_query, *([status] if status else []))

        return {
            'users': [dict(row) for row in rows],
            'total': total,
            'limit': limit,
            'offset': offset,
        }


@router.get('/tenants')
async def list_tenants(
    plan: Optional[str] = None,
    has_k8s: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
    admin: UserSession = Depends(require_admin),
):
    """List all tenants with filtering."""
    pool = await get_pool()
    if not pool:
        raise HTTPException(status_code=503, detail='Database unavailable')

    async with pool.acquire() as conn:
        query = """
            SELECT t.*, 
                   COUNT(u.id) as user_count
            FROM tenants t
            LEFT JOIN users u ON u.tenant_id = t.id
            WHERE 1=1
        """
        params = []
        param_idx = 1

        if plan:
            query += f' AND t.plan = ${param_idx}'
            params.append(plan)
            param_idx += 1

        if has_k8s is not None:
            if has_k8s:
                query += ' AND t.k8s_namespace IS NOT NULL'
            else:
                query += ' AND t.k8s_namespace IS NULL'

        query += f' GROUP BY t.id ORDER BY t.created_at DESC LIMIT ${param_idx} OFFSET ${param_idx + 1}'
        params.extend([limit, offset])

        rows = await conn.fetch(query, *params)

        return {
            'tenants': [dict(row) for row in rows],
            'limit': limit,
            'offset': offset,
        }


@router.get('/instances')
async def list_k8s_instances(
    admin: UserSession = Depends(require_admin),
):
    """List all Kubernetes instances with their status."""
    k8s_stats = await get_k8s_cluster_stats()

    if not k8s_stats:
        return {
            'available': False,
            'message': 'Kubernetes not available or not configured',
            'instances': [],
        }

    return {
        'available': True,
        'summary': {
            'total': k8s_stats.total_namespaces,
            'running': k8s_stats.running_instances,
            'suspended': k8s_stats.suspended_instances,
            'total_pods': k8s_stats.total_pods,
            'healthy_pods': k8s_stats.healthy_pods,
        },
        'instances': [inst.model_dump() for inst in k8s_stats.instances],
    }


@router.post('/instances/{namespace}/scale')
async def scale_instance(
    namespace: str,
    tier: str,
    admin: UserSession = Depends(require_admin),
):
    """Manually scale a K8s instance to a specific tier."""
    try:
        from .k8s_provisioning import k8s_provisioning_service, K8S_AVAILABLE

        if not K8S_AVAILABLE:
            raise HTTPException(
                status_code=503, detail='Kubernetes not available'
            )

        success = await k8s_provisioning_service.scale_instance_for_tier(
            namespace, tier
        )

        if success:
            logger.info(f'Admin {admin.email} scaled {namespace} to {tier}')
            return {'success': True, 'message': f'Instance scaled to {tier}'}
        else:
            raise HTTPException(
                status_code=500, detail='Failed to scale instance'
            )

    except ImportError:
        raise HTTPException(
            status_code=503, detail='K8s provisioning not available'
        )


@router.post('/instances/{namespace}/suspend')
async def suspend_instance(
    namespace: str,
    admin: UserSession = Depends(require_admin),
):
    """Suspend a K8s instance (scale to 0)."""
    try:
        from .k8s_provisioning import k8s_provisioning_service, K8S_AVAILABLE

        if not K8S_AVAILABLE:
            raise HTTPException(
                status_code=503, detail='Kubernetes not available'
            )

        success = await k8s_provisioning_service.suspend_instance(namespace)

        if success:
            logger.info(f'Admin {admin.email} suspended {namespace}')
            return {'success': True, 'message': 'Instance suspended'}
        else:
            raise HTTPException(
                status_code=500, detail='Failed to suspend instance'
            )

    except ImportError:
        raise HTTPException(
            status_code=503, detail='K8s provisioning not available'
        )


@router.post('/instances/{namespace}/resume')
async def resume_instance(
    namespace: str,
    tier: str = 'free',
    admin: UserSession = Depends(require_admin),
):
    """Resume a suspended K8s instance."""
    try:
        from .k8s_provisioning import k8s_provisioning_service, K8S_AVAILABLE

        if not K8S_AVAILABLE:
            raise HTTPException(
                status_code=503, detail='Kubernetes not available'
            )

        success = await k8s_provisioning_service.resume_instance(
            namespace, tier
        )

        if success:
            logger.info(
                f'Admin {admin.email} resumed {namespace} at tier {tier}'
            )
            return {
                'success': True,
                'message': f'Instance resumed at {tier} tier',
            }
        else:
            raise HTTPException(
                status_code=500, detail='Failed to resume instance'
            )

    except ImportError:
        raise HTTPException(
            status_code=503, detail='K8s provisioning not available'
        )


@router.delete('/instances/{namespace}')
async def delete_instance(
    namespace: str,
    admin: UserSession = Depends(require_admin),
):
    """Delete a K8s instance permanently."""
    try:
        from .k8s_provisioning import k8s_provisioning_service, K8S_AVAILABLE

        if not K8S_AVAILABLE:
            raise HTTPException(
                status_code=503, detail='Kubernetes not available'
            )

        success = await k8s_provisioning_service.delete_instance(namespace)

        if success:
            logger.info(f'Admin {admin.email} deleted instance {namespace}')

            # Also clear K8s info from tenant
            pool = await get_pool()
            if pool:
                async with pool.acquire() as conn:
                    await conn.execute(
                        """
                        UPDATE tenants 
                        SET k8s_namespace = NULL, 
                            k8s_external_url = NULL,
                            k8s_internal_url = NULL
                        WHERE k8s_namespace = $1
                    """,
                        namespace,
                    )

            return {'success': True, 'message': 'Instance deleted'}
        else:
            raise HTTPException(
                status_code=500, detail='Failed to delete instance'
            )

    except ImportError:
        raise HTTPException(
            status_code=503, detail='K8s provisioning not available'
        )


@router.get('/health')
async def get_health(admin: UserSession = Depends(require_admin)):
    """Get detailed system health status."""
    return await get_system_health()


@router.get('/alerts')
async def get_system_alerts(admin: UserSession = Depends(require_admin)):
    """Get current system alerts."""
    return await get_alerts()


# ========================================
# OPA Policy Management Endpoints
# ========================================


@router.get('/policy/rbac', response_model=PolicyRBACResponse)
async def get_policy_rbac(
    admin: UserSession = Depends(require_admin),
    _: Dict[str, Any] = Depends(require_permission('admin:manage_policies')),
):
    """Return RBAC role/permission data used by the admin policy editor."""
    data = _load_policy_data_or_error()
    role_map = data.get('roles', {})

    normalized_roles: Dict[str, PolicyRoleDefinition] = {}
    for role_name, role_config in role_map.items():
        if not isinstance(role_name, str) or not isinstance(role_config, dict):
            continue

        normalized_roles[role_name] = PolicyRoleDefinition(
            description=str(role_config.get('description') or ''),
            permissions=sorted(
                {
                    permission
                    for permission in role_config.get('permissions', [])
                    if isinstance(permission, str) and permission.strip()
                }
            ),
            inherits=(
                role_config.get('inherits')
                if isinstance(role_config.get('inherits'), str)
                else None
            ),
        )

    permissions, permissions_by_resource = _build_permission_catalog(role_map)
    return PolicyRBACResponse(
        roles=normalized_roles,
        permissions=permissions,
        permissions_by_resource=permissions_by_resource,
        metadata=_policy_metadata(_policy_data_file()),
    )


@router.put(
    '/policy/roles/{role_name}',
    response_model=UpdatePolicyRoleResponse,
)
async def upsert_policy_role(
    role_name: str,
    request: UpdatePolicyRoleRequest,
    admin: UserSession = Depends(require_admin),
    _: Dict[str, Any] = Depends(require_permission('admin:manage_policies')),
):
    """Create or update one role inside policies/data.json."""
    data = _load_policy_data_or_error()
    roles = data.get('roles', {})
    if not isinstance(roles, dict):
        raise HTTPException(status_code=500, detail='Invalid roles configuration')

    role = _normalize_role(role_name, request, roles)
    role_payload: Dict[str, Any] = {'description': role.description}
    if role.inherits:
        role_payload['inherits'] = role.inherits
    else:
        role_payload['permissions'] = role.permissions

    roles[role_name] = role_payload
    data['roles'] = roles
    _write_policy_data_or_error(data)

    if OPA_LOCAL_MODE:
        try:
            reload_local_policy_data()
        except Exception as e:
            logger.error(f'Failed to reload local policy cache: {e}')
            raise HTTPException(
                status_code=500,
                detail='Role updated, but failed to reload local policy cache',
            ) from e

    logger.info(f"Admin {admin.email} updated OPA role '{role_name}'")
    return UpdatePolicyRoleResponse(
        role_name=role_name,
        role=role,
        metadata=_policy_metadata(_policy_data_file()),
    )


# ========================================
# RBAC User Management (Keycloak + OPA)
# ========================================


@router.get('/rbac/roles', response_model=RBACRoleCatalogResponse)
async def get_rbac_roles(
    realm_name: Optional[str] = Query(default=None),
    admin: UserSession = Depends(require_admin),
    _: Dict[str, Any] = Depends(require_permission('admin:manage_users')),
):
    """Get OPA and Keycloak role catalogs for RBAC management."""
    resolved_realm = _resolve_realm_name(admin, realm_name)
    tenant_id = await _resolve_tenant_id_for_realm(admin, resolved_realm)
    opa_roles = _opa_role_names()

    service = KeycloakTenantService()
    try:
        keycloak_roles = await service.get_realm_roles(resolved_realm)
    except KeycloakTenantServiceError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    missing_in_keycloak = sorted(
        role_name for role_name in opa_roles if role_name not in keycloak_roles
    )

    return RBACRoleCatalogResponse(
        realm_name=resolved_realm,
        opa_roles=opa_roles,
        keycloak_roles=keycloak_roles,
        missing_in_keycloak=missing_in_keycloak,
        metadata={
            'opa_local_mode': OPA_LOCAL_MODE,
            'opa_role_source': str(_policy_data_file()),
            'tenant_id': tenant_id,
            'postgres_rls_enabled': DB_RLS_ENABLED,
            'postgres_sync_enabled': bool(tenant_id),
            'postgres_table': 'rbac_user_roles',
        },
    )


@router.post('/rbac/roles/sync', response_model=RBACSyncRolesResponse)
async def sync_rbac_roles_to_keycloak(
    realm_name: Optional[str] = Query(default=None),
    admin: UserSession = Depends(require_admin),
    _: Dict[str, Any] = Depends(require_permission('admin:manage_users')),
):
    """Create missing Keycloak realm roles for all OPA RBAC roles."""
    resolved_realm = _resolve_realm_name(admin, realm_name)
    opa_roles = _opa_role_names()
    service = KeycloakTenantService()

    try:
        result = await service.ensure_realm_roles(resolved_realm, opa_roles)
    except KeycloakTenantServiceError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    logger.info(
        f"Admin {admin.email} synced OPA roles to Keycloak realm '{resolved_realm}'"
    )
    return RBACSyncRolesResponse(
        realm_name=resolved_realm,
        created=result.get('created', []),
        existing=result.get('existing', []),
        failed=result.get('failed', {}),
    )


@router.get('/rbac/users', response_model=RBACUserListResponse)
async def list_rbac_users(
    realm_name: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    admin: UserSession = Depends(require_admin),
    _: Dict[str, Any] = Depends(require_permission('admin:manage_users')),
):
    """List Keycloak users and their OPA-managed role assignments."""
    resolved_realm = _resolve_realm_name(admin, realm_name)
    service = KeycloakTenantService()
    opa_roles = set(_opa_role_names())
    tenant_id = await _resolve_tenant_id_for_realm(admin, resolved_realm)

    try:
        users = await service.list_realm_users(
            resolved_realm, search=search, first=offset, max_results=limit
        )
    except KeycloakTenantServiceError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    import asyncio

    user_ids = [str(user.get('id')) for user in users if user.get('id')]
    role_lists = await asyncio.gather(
        *[
            service.get_user_realm_roles(resolved_realm, user_id)
            for user_id in user_ids
        ],
        return_exceptions=True,
    )
    roles_by_user_id: Dict[str, List[str]] = {}
    for idx, role_list in enumerate(role_lists):
        if isinstance(role_list, Exception):
            roles_by_user_id[user_ids[idx]] = []
        else:
            roles_by_user_id[user_ids[idx]] = role_list

    db_roles_by_user_id = await _fetch_postgres_rbac_roles(tenant_id, user_ids)
    snapshots_to_upsert: List[Dict[str, Any]] = []

    rows: List[RBACUserSummary] = []
    for user in users:
        user_id = str(user.get('id') or '')
        user_roles = roles_by_user_id.get(user_id, [])
        opa_user_roles = [role for role in user_roles if role in opa_roles]
        db_opa_roles = [
            role
            for role in db_roles_by_user_id.get(user_id, [])
            if role in opa_roles
        ]
        db_synced: Optional[bool]
        if tenant_id:
            db_synced = sorted(opa_user_roles) == sorted(db_opa_roles)
        else:
            db_synced = None
        first_name = user.get('firstName')
        last_name = user.get('lastName')
        full_name = ' '.join(
            part for part in [first_name, last_name] if isinstance(part, str) and part
        ) or None
        snapshots_to_upsert.append(
            {
                'user_id': user_id,
                'email': str(user.get('email') or ''),
                'roles': opa_user_roles,
                'source': 'keycloak_sync',
            }
        )
        rows.append(
            RBACUserSummary(
                id=user_id,
                email=str(user.get('email') or ''),
                username=str(user.get('username') or ''),
                first_name=first_name,
                last_name=last_name,
                name=full_name,
                enabled=bool(user.get('enabled', True)),
                email_verified=bool(user.get('emailVerified', False)),
                roles=user_roles,
                opa_roles=opa_user_roles,
                db_opa_roles=db_opa_roles,
                db_synced=db_synced,
            )
        )

    postgres_synced = await _upsert_postgres_rbac_roles(
        tenant_id=tenant_id,
        realm_name=resolved_realm,
        entries=snapshots_to_upsert,
        updated_by=admin.email,
    )

    return RBACUserListResponse(
        realm_name=resolved_realm,
        users=rows,
        total=len(rows),
        limit=limit,
        offset=offset,
        metadata={
            'opa_roles': sorted(opa_roles),
            'tenant_id': tenant_id,
            'postgres_rls_enabled': DB_RLS_ENABLED,
            'postgres_sync_enabled': bool(tenant_id),
            'postgres_synced': postgres_synced,
            'postgres_table': 'rbac_user_roles',
        },
    )


@router.put('/rbac/users/{user_id}/roles', response_model=RBACUserRoleUpdateResponse)
async def update_rbac_user_roles(
    user_id: str,
    request: RBACUserRoleUpdateRequest,
    admin: UserSession = Depends(require_admin),
    _: Dict[str, Any] = Depends(require_permission('admin:manage_users')),
):
    """
    Update OPA-managed Keycloak realm roles for one user.

    This endpoint only manages roles that exist in OPA data.json.
    """
    resolved_realm = _resolve_realm_name(admin, request.realm_name)
    tenant_id = await _resolve_tenant_id_for_realm(admin, resolved_realm)
    opa_roles = set(_opa_role_names())
    requested_roles = sorted(
        {
            role.strip()
            for role in request.roles
            if isinstance(role, str) and role.strip()
        }
    )

    invalid_roles = [role for role in requested_roles if role not in opa_roles]
    if invalid_roles:
        raise HTTPException(
            status_code=400,
            detail=f"Requested roles are not defined in OPA policy: {', '.join(invalid_roles)}",
        )

    service = KeycloakTenantService()

    if request.sync_missing_roles:
        try:
            await service.ensure_realm_roles(resolved_realm, list(opa_roles))
        except KeycloakTenantServiceError as e:
            raise HTTPException(status_code=502, detail=str(e)) from e

    try:
        result = await service.set_user_realm_roles(
            realm_name=resolved_realm,
            user_id=user_id,
            role_names=requested_roles,
            managed_roles=list(opa_roles),
        )
    except KeycloakTenantServiceError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    logger.info(
        f"Admin {admin.email} updated roles for user {user_id} in realm '{resolved_realm}': {requested_roles}"
    )

    current_opa_roles = [
        role for role in result.get('current', []) if role in opa_roles
    ]
    postgres_synced = await _upsert_postgres_rbac_roles(
        tenant_id=tenant_id,
        realm_name=resolved_realm,
        entries=[
            {
                'user_id': user_id,
                'email': '',
                'roles': current_opa_roles,
                'source': 'admin_update',
            }
        ],
        updated_by=admin.email,
    )

    return RBACUserRoleUpdateResponse(
        realm_name=resolved_realm,
        user_id=user_id,
        assigned=result.get('assigned', []),
        removed=result.get('removed', []),
        roles=result.get('current', []),
        tenant_id=tenant_id,
        postgres_synced=postgres_synced,
        metadata={
            'opa_managed_roles': sorted(opa_roles),
            'postgres_rls_enabled': DB_RLS_ENABLED,
            'postgres_sync_enabled': bool(tenant_id),
            'postgres_table': 'rbac_user_roles',
        },
    )


# ========================================
# Tenant Email Settings Endpoints
# ========================================


class TenantEmailSettingsRequest(BaseModel):
    """Request model for updating tenant email settings."""

    provider: str = 'sendgrid'
    api_key: str
    from_email: str
    from_name: Optional[str] = None
    reply_to_domain: Optional[str] = None
    enabled: bool = True
    daily_limit: int = 1000


class TenantEmailSettingsResponse(BaseModel):
    """Response model for tenant email settings (API key masked)."""

    tenant_id: str
    provider: str
    from_email: str
    from_name: Optional[str]
    reply_to_domain: Optional[str]
    enabled: bool
    daily_limit: int
    emails_sent_today: int
    last_reset_date: str
    created_at: str
    updated_at: str


class TenantEmailStats(BaseModel):
    """Email statistics for a tenant."""

    total_sent: int
    total_failed: int
    sent_last_24h: int
    sent_last_7d: int
    sent_last_30d: int
    quota_usage_percent: float


@router.get('/tenants/{tenant_id}/email-settings')
async def get_tenant_email_settings(
    tenant_id: str,
    admin: UserSession = Depends(require_admin),
) -> TenantEmailSettingsResponse:
    """Get email settings for a tenant (API key is masked)."""
    pool = await get_pool()
    if not pool:
        raise HTTPException(status_code=503, detail='Database not available')

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT 
                tenant_id, provider, from_email, from_name,
                reply_to_domain, enabled, daily_limit,
                emails_sent_today, last_reset_date,
                created_at, updated_at
            FROM tenant_email_settings 
            WHERE tenant_id = $1
            """,
            tenant_id,
        )

        if not row:
            raise HTTPException(
                status_code=404,
                detail=f'Email settings not found for tenant {tenant_id}',
            )

        return TenantEmailSettingsResponse(
            tenant_id=row['tenant_id'],
            provider=row['provider'],
            from_email=row['from_email'],
            from_name=row['from_name'],
            reply_to_domain=row['reply_to_domain'],
            enabled=row['enabled'],
            daily_limit=row['daily_limit'],
            emails_sent_today=row['emails_sent_today'],
            last_reset_date=str(row['last_reset_date']),
            created_at=row['created_at'].isoformat(),
            updated_at=row['updated_at'].isoformat(),
        )


@router.post('/tenants/{tenant_id}/email-settings')
async def update_tenant_email_settings(
    tenant_id: str,
    settings: TenantEmailSettingsRequest,
    admin: UserSession = Depends(require_admin),
) -> TenantEmailSettingsResponse:
    """Update email settings for a tenant."""
    pool = await get_pool()
    if not pool:
        raise HTTPException(status_code=503, detail='Database not available')

    async with pool.acquire() as conn:
        # Encrypt the API key
        encrypted_key = await conn.fetchval(
            "SELECT pgp_sym_encrypt($1, current_setting('app.encryption_key', true))",
            settings.api_key,
        )

        if not encrypted_key:
            raise HTTPException(
                status_code=500, detail='Failed to encrypt API key'
            )

        # Upsert settings
        row = await conn.fetchrow(
            """
            INSERT INTO tenant_email_settings (
                tenant_id, provider, api_key_encrypted, from_email,
                from_name, reply_to_domain, enabled, daily_limit
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (tenant_id) DO UPDATE SET
                provider = EXCLUDED.provider,
                api_key_encrypted = EXCLUDED.api_key_encrypted,
                from_email = EXCLUDED.from_email,
                from_name = EXCLUDED.from_name,
                reply_to_domain = EXCLUDED.reply_to_domain,
                enabled = EXCLUDED.enabled,
                daily_limit = EXCLUDED.daily_limit,
                updated_at = NOW()
            RETURNING 
                tenant_id, provider, from_email, from_name,
                reply_to_domain, enabled, daily_limit,
                emails_sent_today, last_reset_date,
                created_at, updated_at
            """,
            tenant_id,
            settings.provider,
            encrypted_key,
            settings.from_email,
            settings.from_name,
            settings.reply_to_domain,
            settings.enabled,
            settings.daily_limit,
        )

        logger.info(
            f'Admin {admin.email} updated email settings for tenant {tenant_id}'
        )

        return TenantEmailSettingsResponse(
            tenant_id=row['tenant_id'],
            provider=row['provider'],
            from_email=row['from_email'],
            from_name=row['from_name'],
            reply_to_domain=row['reply_to_domain'],
            enabled=row['enabled'],
            daily_limit=row['daily_limit'],
            emails_sent_today=row['emails_sent_today'],
            last_reset_date=str(row['last_reset_date']),
            created_at=row['created_at'].isoformat(),
            updated_at=row['updated_at'].isoformat(),
        )


@router.get('/tenants/{tenant_id}/email-stats')
async def get_tenant_email_stats(
    tenant_id: str,
    days: int = 30,
    admin: UserSession = Depends(require_admin),
) -> TenantEmailStats:
    """Get email sending statistics for a tenant."""
    pool = await get_pool()
    if not pool:
        raise HTTPException(status_code=503, detail='Database not available')

    async with pool.acquire() as conn:
        # Get settings for quota calculation
        settings = await conn.fetchrow(
            'SELECT daily_limit, emails_sent_today FROM tenant_email_settings WHERE tenant_id = $1',
            tenant_id,
        )

        if not settings:
            raise HTTPException(
                status_code=404,
                detail=f'Email settings not found for tenant {tenant_id}',
            )

        # Get stats from outbound_emails table
        stats = await conn.fetchrow(
            """
            SELECT 
                COUNT(*) as total_sent,
                COUNT(CASE WHEN status = 'failed' THEN 1 END) as total_failed,
                COUNT(CASE WHEN created_at > NOW() - INTERVAL '24 hours' THEN 1 END) as sent_last_24h,
                COUNT(CASE WHEN created_at > NOW() - INTERVAL '7 days' THEN 1 END) as sent_last_7d,
                COUNT(CASE WHEN created_at > NOW() - INTERVAL '30 days' THEN 1 END) as sent_last_30d
            FROM outbound_emails 
            WHERE tenant_id = $1
            AND created_at > NOW() - INTERVAL '%s days'
            """,
            tenant_id,
            days,
        )

        quota_usage = (
            settings['emails_sent_today'] / settings['daily_limit'] * 100
            if settings['daily_limit'] > 0
            else 0
        )

        return TenantEmailStats(
            total_sent=stats['total_sent'] or 0,
            total_failed=stats['total_failed'] or 0,
            sent_last_24h=stats['sent_last_24h'] or 0,
            sent_last_7d=stats['sent_last_7d'] or 0,
            sent_last_30d=stats['sent_last_30d'] or 0,
            quota_usage_percent=round(quota_usage, 2),
        )
