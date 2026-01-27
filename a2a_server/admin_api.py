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
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .database import get_pool
from .keycloak_auth import require_admin, UserSession

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


# ========================================
# Data Fetching Functions
# ========================================


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
