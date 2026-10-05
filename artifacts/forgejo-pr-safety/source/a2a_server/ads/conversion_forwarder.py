"""
Conversion Forwarder Worker.

Processes pending conversions from analytics_conversions table
and forwards them to ad platforms (X, Meta, TikTok, Google).

Runs as a background task in the main server or as standalone worker.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

import asyncpg

from .x_conversions import XConversionClient, XConversionEvent

logger = logging.getLogger(__name__)


class ConversionForwarder:
    """
    Background worker that forwards conversions to ad platforms.

    Architecture:
    1. Poll analytics_conversions for pending records
    2. Batch by destination platform
    3. Send via platform-specific client
    4. Mark as forwarded on success, failed on error
    """

    def __init__(
        self,
        db_pool: asyncpg.Pool,
        x_client: XConversionClient | None = None,
        poll_interval: float = 30.0,
        batch_size: int = 100
    ):
        self.db_pool = db_pool
        self.x_client = x_client
        self.poll_interval = poll_interval
        self.batch_size = batch_size
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self):
        """Start the forwarder background task."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Conversion forwarder started")

    async def stop(self):
        """Stop the forwarder gracefully."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Conversion forwarder stopped")

    async def _run_loop(self):
        """Main polling loop."""
        while self._running:
            try:
                await self._process_pending()
            except Exception as e:
                logger.error(f"Error in conversion forwarder: {e}")

            await asyncio.sleep(self.poll_interval)

    async def _process_pending(self):
        """Process all pending conversions."""
        async with self.db_pool.acquire() as conn:
            # Process pending X conversions
            x_rows = await conn.fetch("""
                SELECT id, event_id, conversion_type, conversion_value, currency,
                       email, phone, user_id, workspace_id,
                       x_click_id, occurred_at
                FROM analytics_conversions
                WHERE x_forwarded = FALSE
                  AND x_click_id IS NOT NULL
                ORDER BY occurred_at ASC
                LIMIT $1
            """, self.batch_size)

            if x_rows:
                logger.info(f"Processing {len(x_rows)} pending X conversions")
                await self._forward_to_x(conn, list(x_rows))

            # Process pending FB conversions
            fb_rows = await conn.fetch("""
                SELECT id, event_id, conversion_type, conversion_value, currency,
                       email, phone, user_id, workspace_id,
                       fb_click_id, occurred_at
                FROM analytics_conversions
                WHERE fb_forwarded = FALSE
                  AND fb_click_id IS NOT NULL
                ORDER BY occurred_at ASC
                LIMIT $1
            """, self.batch_size)

            if fb_rows:
                logger.info(f"Processing {len(fb_rows)} pending FB conversions")
                await self._forward_to_meta(conn, list(fb_rows))

            # Process pending Google conversions
            google_rows = await conn.fetch("""
                SELECT id, event_id, conversion_type, conversion_value, currency,
                       email, phone, user_id, workspace_id,
                       google_click_id, occurred_at
                FROM analytics_conversions
                WHERE google_forwarded = FALSE
                  AND google_click_id IS NOT NULL
                ORDER BY occurred_at ASC
                LIMIT $1
            """, self.batch_size)

            if google_rows:
                logger.info(f"Processing {len(google_rows)} pending Google conversions")
                await self._forward_to_google(conn, list(google_rows))

    async def _forward_to_x(
        self,
        conn: asyncpg.Connection,
        records: list[asyncpg.Record]
    ):
        """Forward conversions to X Ads API."""
        if not self.x_client:
            logger.warning("X client not configured, skipping X conversions")
            return

        events = []
        record_ids = []

        for row in records:
            event = XConversionEvent(
                event_type=self._map_event_type(row['conversion_type']),
                twclid=row.get('x_click_id'),
                email=row.get('email'),
                phone=row.get('phone'),
                value=float(row['conversion_value']) if row['conversion_value'] else None,
                event_id=str(row['id']),
                conversion_id=str(row['id'])
            )
            events.append(event)
            record_ids.append(row['id'])

        try:
            results = await self.x_client.send_batch(events)
            logger.info(f"Forwarded {len(events)} conversions to X")

            # Mark as forwarded
            await conn.execute("""
                UPDATE analytics_conversions
                SET x_forwarded = TRUE,
                    x_forwarded_at = NOW(),
                    x_response = $2
                WHERE id = ANY($1)
            """, record_ids, json.dumps(results))

        except Exception as e:
            logger.error(f"Failed to forward to X: {e}")

            # Mark with error in response field
            await conn.execute("""
                UPDATE analytics_conversions
                SET x_response = $2
                WHERE id = ANY($1)
            """, record_ids, json.dumps({'error': str(e)}))
        # TODO: Implement Meta Conversion API
        # For now, bridge to spotlessbinco
        logger.warning("Meta forwarding not yet implemented")

    async def _forward_to_tiktok(
        self,
        conn: asyncpg.Connection,
        records: list[asyncpg.Record]
    ):
        """Forward conversions to TikTok Events API."""
        # TODO: Implement TikTok Events API
        # For now, bridge to spotlessbinco
        logger.warning("TikTok forwarding not yet implemented")

    async def _forward_to_google(
        self,
        conn: asyncpg.Connection,
        records: list[asyncpg.Record]
    ):
        """Forward conversions to Google Ads API."""
        # TODO: Implement Google Ads Conversion API
        # For now, bridge to spotlessbinco
        logger.warning("Google forwarding not yet implemented")

    @staticmethod
    def _map_event_type(internal_type: str) -> str:
        """Map internal event types to X API types."""
        mapping = {
            'signup': 'SIGNUP',
            'purchase': 'PURCHASE',
            'lead': 'LEAD',
            'download': 'DOWNLOAD',
            'add_to_cart': 'ADD_TO_CART',
            'checkout': 'CHECKOUT_INITIATED',
            'page_view': 'PAGE_VIEW',
            'search': 'SEARCH'
        }
        return mapping.get(internal_type.lower(), 'CUSTOM')


async def create_forwarder(
    db_pool: asyncpg.Pool,
    x_pixel_id: str | None = None,
    x_consumer_key: str | None = None,
    x_consumer_secret: str | None = None,
    x_access_token: str | None = None,
    x_access_token_secret: str | None = None
) -> ConversionForwarder:
    """Factory function to create configured forwarder."""
    import os

    # Build X client if credentials available
    x_client = None
    pixel_id = x_pixel_id or os.environ.get("X_ADS_PIXEL_ID")

    if pixel_id:
        x_client = XConversionClient(
            pixel_id=pixel_id,
            consumer_key=x_consumer_key or os.environ.get("X_ADS_CONSUMER_KEY", ""),
            consumer_secret=x_consumer_secret or os.environ.get("X_ADS_CONSUMER_SECRET", ""),
            access_token=x_access_token or os.environ.get("X_ADS_ACCESS_TOKEN", ""),
            access_token_secret=x_access_token_secret or os.environ.get("X_ADS_ACCESS_TOKEN_SECRET", "")
        )
        logger.info(f"X Ads client configured with pixel: {pixel_id}")
    else:
        logger.warning("X Ads credentials not configured")

    return ConversionForwarder(
        db_pool=db_pool,
        x_client=x_client
    )
