"""
Conversion Tracker — closes the feedback loop between user signups/subscriptions
and the marketing optimization systems (FunnelBrain + Google Ads).

When a user signs up, starts a trial, or subscribes via Stripe, this module:
1. Records the conversion event locally in conversion_events table
2. Forwards to FunnelBrain (POST /api/optimization/assemble) to update Thompson Sampling
3. Forwards to Google Ads Enhanced Conversions (POST /api/google/conversions?action=track)
4. Publishes a rule engine event for downstream automation

Also manages FunnelBrain state persistence:
- Periodically exports FunnelBrain state from the marketing-site
- Stores snapshots in funnel_state_snapshots table
- Restores state on marketing-site restart

Usage:
    from .conversion_tracker import track_conversion, get_conversion_tracker
    await track_conversion(
        event_type='subscription',
        email='user@example.com',
        value_dollars=29.0,
    )
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Configuration
CONVERSION_TRACKING_ENABLED = os.environ.get(
    'CONVERSION_TRACKING_ENABLED', 'true'
).lower() == 'true'
FUNNEL_PERSIST_INTERVAL = int(os.environ.get('FUNNEL_PERSIST_INTERVAL_SECONDS', '900'))

# Value map for conversion events (dollars)
DEFAULT_CONVERSION_VALUES = {
    'signup': 5.0,
    'trial_start': 15.0,
    'subscription': 29.0,
    'subscription_upgrade': 49.0,
}


class ConversionTracker:
    """
    Tracks conversion events and persists FunnelBrain state.

    Two responsibilities:
    1. Forward user conversion events to marketing-site APIs
    2. Periodically snapshot FunnelBrain state to DB for durability
    """

    def __init__(self, persist_interval: int = FUNNEL_PERSIST_INTERVAL):
        self.persist_interval = persist_interval
        self._running = False
        self._persist_task: Optional[asyncio.Task] = None
        self._conversions_tracked = 0
        self._last_persist: Optional[datetime] = None
        self._last_conversions_forwarded: Optional[datetime] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._persist_task = asyncio.create_task(self._persist_loop())
        logger.info(
            'ConversionTracker started (persist_interval=%ds)',
            self.persist_interval,
        )

    async def stop(self) -> None:
        self._running = False
        if self._persist_task:
            self._persist_task.cancel()
            try:
                await self._persist_task
            except asyncio.CancelledError:
                pass
            self._persist_task = None
        logger.info('ConversionTracker stopped')

    # ------------------------------------------------------------------
    # Core: Track a conversion
    # ------------------------------------------------------------------

    async def track(
        self,
        event_type: str,
        email: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        gclid: Optional[str] = None,
        variant_ids: Optional[Dict[str, str]] = None,
        value_dollars: Optional[float] = None,
        order_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Track a conversion event end-to-end.

        1. Store locally in conversion_events table
        2. Forward to FunnelBrain for Thompson Sampling update
        3. Forward to Google Ads Enhanced Conversions
        4. Publish rule engine event

        Args:
            event_type: signup | trial_start | subscription | subscription_upgrade
            email: User email (hashed before sending to Google Ads)
            user_id: Internal user ID
            session_id: Browser session for FunnelBrain attribution
            gclid: Google Click ID for conversion attribution
            variant_ids: FunnelBrain variant selections (slot → variant_id)
            value_dollars: Conversion value (defaults from DEFAULT_CONVERSION_VALUES)
            order_id: Order/subscription ID for deduplication
            metadata: Additional context

        Returns:
            conversion_id on success, None on failure
        """
        if not CONVERSION_TRACKING_ENABLED:
            return None

        value = value_dollars or DEFAULT_CONVERSION_VALUES.get(event_type, 0.0)
        conversion_id = str(uuid.uuid4())

        # 1. Store locally
        await self._store_conversion(
            conversion_id=conversion_id,
            event_type=event_type,
            email=email,
            user_id=user_id,
            session_id=session_id,
            gclid=gclid,
            variant_ids=variant_ids,
            value_dollars=value,
            order_id=order_id,
            metadata=metadata,
        )

        # 2-3. Forward to marketing-site APIs (fire-and-forget, don't block caller)
        asyncio.create_task(self._forward_conversion(
            conversion_id=conversion_id,
            event_type=event_type,
            email=email,
            session_id=session_id,
            gclid=gclid,
            variant_ids=variant_ids,
            value_dollars=value,
            order_id=order_id,
        ))

        # 4. Publish rule engine event
        asyncio.create_task(self._publish_conversion_event(
            event_type=event_type,
            value_dollars=value,
            user_id=user_id,
        ))

        self._conversions_tracked += 1
        self._last_conversions_forwarded = datetime.now(timezone.utc)

        return conversion_id

    # ------------------------------------------------------------------
    # Step 1: Local storage
    # ------------------------------------------------------------------

    async def _store_conversion(
        self,
        conversion_id: str,
        event_type: str,
        email: Optional[str],
        user_id: Optional[str],
        session_id: Optional[str],
        gclid: Optional[str],
        variant_ids: Optional[Dict[str, str]],
        value_dollars: float,
        order_id: Optional[str],
        metadata: Optional[Dict[str, Any]],
    ) -> None:
        """Store conversion event in the local database."""
        try:
            from . import database as db

            pool = await db.get_pool()
            if not pool:
                return

            async with pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO conversion_events
                        (id, event_type, email, user_id, session_id, gclid,
                         variant_ids, value_dollars, order_id, metadata,
                         funnel_forwarded, google_forwarded, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8, $9, $10::jsonb,
                            FALSE, FALSE, NOW())
                """,
                    conversion_id, event_type, email, user_id, session_id, gclid,
                    json.dumps(variant_ids or {}),
                    value_dollars, order_id,
                    json.dumps(metadata or {}),
                )
        except Exception as e:
            logger.error('Failed to store conversion event: %s', e)

    # ------------------------------------------------------------------
    # Steps 2-3: Forward to marketing-site
    # ------------------------------------------------------------------

    async def _forward_conversion(
        self,
        conversion_id: str,
        event_type: str,
        email: Optional[str],
        session_id: Optional[str],
        gclid: Optional[str],
        variant_ids: Optional[Dict[str, str]],
        value_dollars: float,
        order_id: Optional[str],
    ) -> None:
        """Forward conversion to FunnelBrain and Google Ads."""
        funnel_ok = False
        google_ok = False

        # Forward to FunnelBrain (Thompson Sampling update)
        if session_id or variant_ids:
            funnel_ok = await self._forward_to_funnel_brain(
                session_id=session_id or conversion_id,
                event_type=event_type,
                variant_ids=variant_ids,
                value_cents=int(value_dollars * 100),
            )

        # Forward to Google Ads (Enhanced Conversions)
        if email or gclid:
            google_ok = await self._forward_to_google_ads(
                event_type=event_type,
                email=email,
                gclid=gclid,
                value_dollars=value_dollars,
                order_id=order_id,
            )

        # Update forwarding status
        await self._update_forwarding_status(conversion_id, funnel_ok, google_ok)

    async def _forward_to_funnel_brain(
        self,
        session_id: str,
        event_type: str,
        variant_ids: Optional[Dict[str, str]],
        value_cents: int,
    ) -> bool:
        """POST conversion to FunnelBrain via /api/optimization/assemble."""
        try:
            from .http_client import http_request, CircuitBreakerOpenError

            resp = await http_request(
                'POST', '/api/optimization/assemble',
                json={
                    'sessionId': session_id,
                    'eventType': event_type,
                    'variantIds': variant_ids or {},
                    'valueCents': value_cents,
                },
                timeout=15.0,
            )
            if resp.status_code == 200:
                logger.debug('FunnelBrain conversion recorded: %s', event_type)
                return True
            else:
                logger.warning(
                    'FunnelBrain conversion failed: %d %s',
                    resp.status_code, resp.text[:200],
                )
                return False
        except CircuitBreakerOpenError:
            logger.warning('FunnelBrain forward skipped: circuit breaker open')
            return False
        except Exception as e:
            logger.warning('FunnelBrain forward error: %s', e)
            return False

    async def _forward_to_google_ads(
        self,
        event_type: str,
        email: Optional[str],
        gclid: Optional[str],
        value_dollars: float,
        order_id: Optional[str],
    ) -> bool:
        """POST conversion to Google Ads via /api/google/conversions?action=track."""
        try:
            from .http_client import http_request, CircuitBreakerOpenError

            resp = await http_request(
                'POST', '/api/google/conversions',
                params={'action': 'track'},
                json={
                    'eventType': event_type,
                    'email': email,
                    'gclid': gclid,
                    'valueDollars': value_dollars,
                    'orderId': order_id,
                },
                timeout=15.0,
            )
            if resp.status_code == 200:
                logger.debug('Google Ads conversion tracked: %s', event_type)
                return True
            else:
                logger.warning(
                    'Google Ads conversion failed: %d %s',
                    resp.status_code, resp.text[:200],
                )
                return False
        except CircuitBreakerOpenError:
            logger.warning('Google Ads forward skipped: circuit breaker open')
            return False
        except Exception as e:
            logger.warning('Google Ads forward error: %s', e)
            return False

    async def _update_forwarding_status(
        self, conversion_id: str, funnel_ok: bool, google_ok: bool
    ) -> None:
        """Update forwarding flags on the stored conversion event."""
        try:
            from . import database as db

            pool = await db.get_pool()
            if not pool:
                return

            async with pool.acquire() as conn:
                await conn.execute("""
                    UPDATE conversion_events
                    SET funnel_forwarded = $2, google_forwarded = $3
                    WHERE id = $1
                """, conversion_id, funnel_ok, google_ok)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Step 4: Rule engine event
    # ------------------------------------------------------------------

    async def _publish_conversion_event(
        self,
        event_type: str,
        value_dollars: float,
        user_id: Optional[str],
    ) -> None:
        """Publish a conversion event to the rule engine for downstream automation."""
        try:
            from .rule_engine import get_rule_engine
            engine = get_rule_engine()
            if engine:
                await engine.evaluate_event_rules(f'conversion.{event_type}', {
                    'event_type': event_type,
                    'value_dollars': value_dollars,
                    'user_id': user_id,
                })
        except Exception:
            pass

    # ------------------------------------------------------------------
    # FunnelBrain State Persistence
    # ------------------------------------------------------------------

    async def _persist_loop(self) -> None:
        """Periodically export FunnelBrain state and save to DB."""
        await asyncio.sleep(60)  # initial delay

        while self._running:
            try:
                await self._snapshot_funnel_state()
                self._last_persist = datetime.now(timezone.utc)
            except Exception as e:
                logger.error('FunnelBrain persist error: %s', e, exc_info=True)

            await asyncio.sleep(self.persist_interval)

    async def _snapshot_funnel_state(self) -> None:
        """Export FunnelBrain state from marketing-site and save to DB."""
        try:
            from .http_client import http_request, CircuitBreakerOpenError

            resp = await http_request('GET', '/api/optimization/report', timeout=15.0)

            if resp.status_code != 200:
                return

            report = resp.json()
            funnel_data = report.get('funnelBrain', {})
            ad_data = report.get('adBrain', {})

            from . import database as db
            pool = await db.get_pool()
            if not pool:
                return

            snapshot_id = str(uuid.uuid4())
            async with pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO funnel_state_snapshots
                        (id, funnel_brain_state, ad_brain_state, created_at)
                    VALUES ($1, $2::jsonb, $3::jsonb, NOW())
                """,
                    snapshot_id,
                    json.dumps(funnel_data, default=str),
                    json.dumps(ad_data, default=str),
                )

                # Prune old snapshots (keep last 100)
                await conn.execute("""
                    DELETE FROM funnel_state_snapshots
                    WHERE id NOT IN (
                        SELECT id FROM funnel_state_snapshots
                        ORDER BY created_at DESC LIMIT 100
                    )
                """)

            logger.debug('FunnelBrain state snapshot saved: %s', snapshot_id)

        except Exception as e:
            logger.warning('FunnelBrain snapshot fetch error: %s', e)

    async def restore_funnel_state(self) -> Optional[Dict[str, Any]]:
        """
        Load the latest FunnelBrain state snapshot from DB.

        Returns the snapshot data for the caller to push to the marketing-site.
        """
        try:
            from . import database as db
            pool = await db.get_pool()
            if not pool:
                return None

            async with pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT funnel_brain_state, ad_brain_state, created_at
                    FROM funnel_state_snapshots
                    ORDER BY created_at DESC LIMIT 1
                """)

            if not row:
                return None

            return {
                'funnelBrain': row['funnel_brain_state'],
                'adBrain': row['ad_brain_state'],
                'snapshotAt': row['created_at'].isoformat() if row['created_at'] else None,
            }
        except Exception as e:
            logger.error('FunnelBrain state restore failed: %s', e)
            return None

    # ------------------------------------------------------------------
    # Conversion analytics
    # ------------------------------------------------------------------

    async def get_conversion_stats(
        self, days: int = 30
    ) -> Dict[str, Any]:
        """Get conversion statistics for the last N days."""
        try:
            from . import database as db
            pool = await db.get_pool()
            if not pool:
                return {}

            async with pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT event_type,
                           COUNT(*) as count,
                           SUM(value_dollars) as total_value,
                           AVG(value_dollars) as avg_value,
                           COUNT(*) FILTER (WHERE funnel_forwarded) as funnel_tracked,
                           COUNT(*) FILTER (WHERE google_forwarded) as google_tracked
                    FROM conversion_events
                    WHERE created_at >= NOW() - ($1 || ' days')::interval
                    GROUP BY event_type
                    ORDER BY count DESC
                """, str(days))

                return {
                    'period_days': days,
                    'by_type': [
                        {
                            'event_type': r['event_type'],
                            'count': r['count'],
                            'total_value': float(r['total_value'] or 0),
                            'avg_value': float(r['avg_value'] or 0),
                            'funnel_tracked': r['funnel_tracked'],
                            'google_tracked': r['google_tracked'],
                        }
                        for r in rows
                    ],
                    'total_conversions': sum(r['count'] for r in rows),
                    'total_value': sum(float(r['total_value'] or 0) for r in rows),
                }
        except Exception as e:
            logger.error('Conversion stats query failed: %s', e)
            return {}

    # ------------------------------------------------------------------
    # Retry failed forwards
    # ------------------------------------------------------------------

    async def retry_failed_forwards(self, limit: int = 50) -> int:
        """
        Retry conversion events that failed to forward to marketing-site.

        Returns the number of retried events.
        """
        try:
            from . import database as db
            pool = await db.get_pool()
            if not pool:
                return 0

            async with pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT id, event_type, email, session_id, gclid,
                           variant_ids, value_dollars, order_id,
                           funnel_forwarded, google_forwarded
                    FROM conversion_events
                    WHERE (NOT funnel_forwarded OR NOT google_forwarded)
                      AND created_at >= NOW() - interval '7 days'
                    ORDER BY created_at ASC
                    LIMIT $1
                """, limit)

            retried = 0
            for row in rows:
                await self._forward_conversion(
                    conversion_id=row['id'],
                    event_type=row['event_type'],
                    email=row['email'],
                    session_id=row['session_id'],
                    gclid=row['gclid'],
                    variant_ids=json.loads(row['variant_ids']) if isinstance(row['variant_ids'], str) else (row['variant_ids'] or {}),
                    value_dollars=float(row['value_dollars'] or 0),
                    order_id=row.get('order_id'),
                )
                retried += 1

            if retried:
                logger.info('Retried %d failed conversion forwards', retried)

            return retried

        except Exception as e:
            logger.error('Conversion retry failed: %s', e)
            return 0

    def get_health(self) -> Dict[str, Any]:
        return {
            'running': self._running,
            'enabled': CONVERSION_TRACKING_ENABLED,
            'conversions_tracked': self._conversions_tracked,
            'last_conversion': (
                self._last_conversions_forwarded.isoformat()
                if self._last_conversions_forwarded else None
            ),
            'last_funnel_persist': (
                self._last_persist.isoformat() if self._last_persist else None
            ),
            'persist_interval_seconds': self.persist_interval,
        }


# ============================================================================
# Global instance management
# ============================================================================

_tracker: Optional[ConversionTracker] = None


def get_conversion_tracker() -> Optional[ConversionTracker]:
    return _tracker


async def start_conversion_tracker() -> ConversionTracker:
    global _tracker
    if _tracker is not None:
        return _tracker
    _tracker = ConversionTracker()
    await _tracker.start()
    return _tracker


async def stop_conversion_tracker() -> None:
    global _tracker
    if _tracker:
        await _tracker.stop()
        _tracker = None


# ============================================================================
# Convenience function — can be called from anywhere
# ============================================================================


async def track_conversion(
    event_type: str,
    email: Optional[str] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    gclid: Optional[str] = None,
    variant_ids: Optional[Dict[str, str]] = None,
    value_dollars: Optional[float] = None,
    order_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Track a conversion event. Safe to call from any code path.

    Returns conversion_id on success, None if tracker is not running.
    """
    tracker = get_conversion_tracker()
    if not tracker:
        logger.debug('Conversion tracking skipped: tracker not running')
        return None

    return await tracker.track(
        event_type=event_type,
        email=email,
        user_id=user_id,
        session_id=session_id,
        gclid=gclid,
        variant_ids=variant_ids,
        value_dollars=value_dollars,
        order_id=order_id,
        metadata=metadata,
    )
