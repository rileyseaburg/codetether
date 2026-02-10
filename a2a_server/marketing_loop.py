"""
Marketing Perpetual Loop — auto-starts a marketer persona perpetual cognition loop.

The marketer persona (created by migration 020) needs a perpetual loop that
maintains strategic context across iterations: learning what campaigns work,
tracking conversion trends, and adjusting the marketing mix.

This module:
1. Checks on startup if a marketer loop already exists
2. If not, creates one with the right parameters
3. Wires the orchestrator to respond to loop-generated events

The loop iterates daily, analyzing marketing data and making strategic decisions
that feed into the rule engine and orchestrator.

Usage:
    from .marketing_loop import ensure_marketing_loop
    await ensure_marketing_loop()
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

MARKETING_LOOP_ENABLED = os.environ.get(
    'MARKETING_LOOP_ENABLED', 'true'
).lower() == 'true'

# Default loop parameters
DEFAULT_INTERVAL = int(os.environ.get('MARKETING_LOOP_INTERVAL_SECONDS', '86400'))  # daily
DEFAULT_MAX_ITERATIONS = int(os.environ.get('MARKETING_LOOP_MAX_DAILY', '2'))
DEFAULT_COST_CEILING = int(os.environ.get('MARKETING_LOOP_COST_CEILING_CENTS', '200'))

MARKETING_LOOP_ID = 'loop-marketing-strategist'


async def ensure_marketing_loop() -> Optional[str]:
    """
    Ensure a marketing strategist perpetual loop exists and is running.

    Idempotent: if the loop already exists, it will be resumed if paused.
    If it doesn't exist, it will be created.

    Returns:
        loop_id if created/resumed, None if disabled or failed
    """
    if not MARKETING_LOOP_ENABLED:
        logger.info('Marketing loop disabled via MARKETING_LOOP_ENABLED')
        return None

    try:
        from . import database as db

        pool = await db.get_pool()
        if not pool:
            logger.warning('Marketing loop: database not available')
            return None

        async with pool.acquire() as conn:
            # Check if marketer persona exists
            persona = await conn.fetchrow(
                "SELECT slug FROM worker_profiles WHERE slug = 'marketer'"
            )
            if not persona:
                logger.info('Marketing loop: marketer persona not found, skipping')
                return None

            # Check if loop already exists
            existing = await conn.fetchrow(
                "SELECT id, status FROM perpetual_loops WHERE id = $1",
                MARKETING_LOOP_ID,
            )

            if existing:
                if existing['status'] in ('paused', 'budget_exhausted'):
                    # Resume
                    await conn.execute("""
                        UPDATE perpetual_loops
                        SET status = 'running', updated_at = NOW()
                        WHERE id = $1
                    """, MARKETING_LOOP_ID)
                    logger.info('Marketing loop resumed: %s', MARKETING_LOOP_ID)
                else:
                    logger.info(
                        'Marketing loop already exists (status=%s)',
                        existing['status'],
                    )
                return MARKETING_LOOP_ID

            # Create the loop with strategic initial state
            initial_state = _build_initial_state()

            await conn.execute("""
                INSERT INTO perpetual_loops
                    (id, persona_slug, status, state,
                     iteration_interval_seconds, max_iterations_per_day,
                     daily_cost_ceiling_cents, created_at, updated_at)
                VALUES ($1, 'marketer', 'running', $2::jsonb, $3, $4, $5, NOW(), NOW())
            """,
                MARKETING_LOOP_ID,
                json.dumps(initial_state, default=str),
                DEFAULT_INTERVAL,
                DEFAULT_MAX_ITERATIONS,
                DEFAULT_COST_CEILING,
            )

            logger.info(
                'Marketing perpetual loop created: %s (interval=%ds, max=%d/day)',
                MARKETING_LOOP_ID, DEFAULT_INTERVAL, DEFAULT_MAX_ITERATIONS,
            )

            # Audit log
            from .audit_log import log_decision
            await log_decision(
                source='marketing_loop',
                decision_type='loop_created',
                description=(
                    f'Marketing strategist perpetual loop created '
                    f'(interval={DEFAULT_INTERVAL}s, max={DEFAULT_MAX_ITERATIONS}/day)'
                ),
                decision_data={
                    'loop_id': MARKETING_LOOP_ID,
                    'interval': DEFAULT_INTERVAL,
                    'max_daily': DEFAULT_MAX_ITERATIONS,
                    'cost_ceiling_cents': DEFAULT_COST_CEILING,
                },
            )

            return MARKETING_LOOP_ID

    except Exception as e:
        logger.error('Failed to ensure marketing loop: %s', e)
        return None


def _build_initial_state() -> Dict[str, Any]:
    """Build the initial state for the marketing strategist loop."""
    return {
        'strategy_version': 1,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'focus_areas': [
            'conversion_rate_optimization',
            'cost_per_acquisition',
            'channel_mix_efficiency',
        ],
        'kpis': {
            'target_roas': 3.0,
            'target_cpa_dollars': 30.0,
            'target_conversion_rate': 0.05,
        },
        'channels_active': [
            'google_ads_search',
            'google_ads_video',
            'organic_seo',
        ],
        'learnings': [],
        'last_analysis': None,
        'iteration_history': [],
    }
