"""
CodeTether First-Party Analytics API.

Phase 1 of vertical integration - CodeTether owns the event stream.

This module provides:
- Event ingestion (track_event)
- Identity stitching (identify)
- Funnel analytics (get_funnel_metrics)
- Attribution (get_attribution)
- Conversion forwarding queue management

Endpoints:
    POST /v1/analytics/track     - Track an event
    POST /v1/analytics/identify  - Link anonymous ID to user
    POST /v1/analytics/page      - Track page view (convenience)
    GET  /v1/analytics/funnel    - Get funnel metrics
    GET  /v1/analytics/attribution/{user_id} - Get attribution data
"""

import hashlib
import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from .database import get_pool

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/v1/analytics', tags=['Analytics'])


# ============================================================================
# Configuration
# ============================================================================

# Conversion event types that should be forwarded to ad platforms
CONVERSION_EVENTS = {
    'signup_completed',
    'trial_started',
    'first_success',
    'paid',
    'upgrade',
}


# ============================================================================
# Request/Response Models
# ============================================================================


class EventCategory(str, Enum):
    """Event categories for classification."""
    ENGAGEMENT = 'engagement'
    CONVERSION = 'conversion'
    RETENTION = 'retention'
    SYSTEM = 'system'


class TrackEventRequest(BaseModel):
    """Request to track an event."""
    
    event_type: str = Field(..., description='Event type (e.g., page_view, signup_completed)')
    anonymous_id: str = Field(..., description='Anonymous visitor ID (cookie/device ID)')
    
    # Optional identity (filled in after signup)
    user_id: Optional[str] = None
    workspace_id: Optional[str] = None
    session_id: Optional[str] = None
    
    # Attribution (captured on first touch)
    referrer: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    utm_term: Optional[str] = None
    utm_content: Optional[str] = None
    landing_page: Optional[str] = None
    
    # Context
    page_url: Optional[str] = None
    page_title: Optional[str] = None
    
    # Click IDs for ad attribution
    x_click_id: Optional[str] = None      # twclid
    fb_click_id: Optional[str] = None     # fbclid
    google_click_id: Optional[str] = None  # gclid
    
    # Flexible properties
    properties: Dict[str, Any] = Field(default_factory=dict)
    
    # Conversion value (for purchase events)
    conversion_value: Optional[float] = None
    currency: str = 'USD'
    
    # Timestamp (defaults to now)
    timestamp: Optional[datetime] = None


class TrackEventResponse(BaseModel):
    """Response from tracking an event."""
    success: bool
    event_id: str
    message: str = 'Event tracked'


class IdentifyRequest(BaseModel):
    """Request to link anonymous ID to a known user."""
    
    anonymous_id: str = Field(..., description='Anonymous visitor ID')
    user_id: Optional[str] = None
    workspace_id: Optional[str] = None
    email: Optional[str] = None
    
    # Additional traits to store
    traits: Dict[str, Any] = Field(default_factory=dict)


class IdentifyResponse(BaseModel):
    """Response from identify call."""
    success: bool
    message: str


class PageViewRequest(BaseModel):
    """Convenience model for page view tracking."""
    
    anonymous_id: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    
    page_url: str
    page_title: Optional[str] = None
    referrer: Optional[str] = None
    
    # UTM params
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    utm_term: Optional[str] = None
    utm_content: Optional[str] = None
    
    # Click IDs
    x_click_id: Optional[str] = None
    fb_click_id: Optional[str] = None
    google_click_id: Optional[str] = None


class FunnelStep(BaseModel):
    """A step in the funnel with metrics."""
    step_name: str
    event_type: str
    count: int
    conversion_rate: float  # From previous step
    overall_rate: float     # From funnel start


class FunnelMetricsResponse(BaseModel):
    """Funnel analysis response."""
    funnel_name: str
    date_range_start: datetime
    date_range_end: datetime
    total_entered: int
    total_converted: int
    overall_conversion_rate: float
    steps: List[FunnelStep]


class AttributionData(BaseModel):
    """Attribution data for a user."""
    user_id: str
    
    # First touch attribution
    first_touch_source: Optional[str] = None
    first_touch_medium: Optional[str] = None
    first_touch_campaign: Optional[str] = None
    first_touch_at: Optional[datetime] = None
    
    # Last touch attribution
    last_touch_source: Optional[str] = None
    last_touch_medium: Optional[str] = None
    last_touch_campaign: Optional[str] = None
    last_touch_at: Optional[datetime] = None
    
    # Conversion touch (at time of conversion)
    conversion_source: Optional[str] = None
    conversion_medium: Optional[str] = None
    conversion_campaign: Optional[str] = None
    conversion_at: Optional[datetime] = None


# ============================================================================
# Helper Functions
# ============================================================================


def extract_client_info(request: Request) -> Dict[str, Any]:
    """Extract client info from request headers."""
    return {
        'user_agent': request.headers.get('user-agent'),
        'ip_address': request.headers.get('x-forwarded-for', request.client.host if request.client else None),
    }


def categorize_event(event_type: str) -> str:
    """Determine event category."""
    if event_type in CONVERSION_EVENTS:
        return EventCategory.CONVERSION.value
    if event_type in ('page_view', 'click', 'scroll', 'focus'):
        return EventCategory.ENGAGEMENT.value
    if event_type in ('session_start', 'return_visit', 'feature_used'):
        return EventCategory.RETENTION.value
    return EventCategory.SYSTEM.value


# ============================================================================
# Endpoints
# ============================================================================


@router.post('/track', response_model=TrackEventResponse)
async def track_event(
    req: TrackEventRequest,
    request: Request,
) -> TrackEventResponse:
    """
    Track an analytics event.
    
    This is the core event ingestion endpoint. All user interactions
    flow through here.
    
    For conversion events (signup_completed, trial_started, paid),
    a record is also created in analytics_conversions for forwarding
    to ad platforms.
    """
    pool = await get_pool()
    if not pool:
        raise HTTPException(status_code=503, detail='Database unavailable')
    
    event_id = str(uuid.uuid4())
    event_time = req.timestamp or datetime.now(timezone.utc)
    event_category = categorize_event(req.event_type)
    client_info = extract_client_info(request)
    
    async with pool.acquire() as conn:
        # Insert event
        await conn.execute(
            '''
            INSERT INTO analytics_events (
                id, event_time, event_type, event_category,
                anonymous_id, user_id, workspace_id, session_id,
                referrer, utm_source, utm_medium, utm_campaign, utm_term, utm_content,
                landing_page, page_url, page_title, user_agent, ip_address,
                properties, conversion_value, currency
            ) VALUES (
                $1, $2, $3, $4,
                $5, $6, $7, $8,
                $9, $10, $11, $12, $13, $14,
                $15, $16, $17, $18, $19::inet,
                $20, $21, $22
            )
            ''',
            event_id, event_time, req.event_type, event_category,
            req.anonymous_id, req.user_id, req.workspace_id, req.session_id,
            req.referrer, req.utm_source, req.utm_medium, req.utm_campaign, 
            req.utm_term, req.utm_content,
            req.landing_page, req.page_url, req.page_title, 
            client_info.get('user_agent'), client_info.get('ip_address'),
            json.dumps(req.properties), req.conversion_value, req.currency,
        )
        
        # Update identity map (upsert)
        await conn.execute(
            '''
            INSERT INTO analytics_identity_map (anonymous_id, user_id, workspace_id, last_seen_at)
            VALUES ($1, $2, $3, NOW())
            ON CONFLICT (anonymous_id) DO UPDATE SET
                user_id = COALESCE(EXCLUDED.user_id, analytics_identity_map.user_id),
                workspace_id = COALESCE(EXCLUDED.workspace_id, analytics_identity_map.workspace_id),
                last_seen_at = NOW(),
                user_linked_at = CASE 
                    WHEN EXCLUDED.user_id IS NOT NULL AND analytics_identity_map.user_id IS NULL 
                    THEN NOW() 
                    ELSE analytics_identity_map.user_linked_at 
                END,
                workspace_linked_at = CASE 
                    WHEN EXCLUDED.workspace_id IS NOT NULL AND analytics_identity_map.workspace_id IS NULL 
                    THEN NOW() 
                    ELSE analytics_identity_map.workspace_linked_at 
                END
            ''',
            req.anonymous_id, req.user_id, req.workspace_id,
        )
        
        # Create first-touch touchpoint if this is the first event for this anonymous_id
        await conn.execute(
            '''
            INSERT INTO analytics_touchpoints (
                anonymous_id, user_id, workspace_id, touchpoint_type,
                referrer, utm_source, utm_medium, utm_campaign, utm_term, utm_content,
                landing_page, event_id, event_type
            )
            SELECT $1, $2, $3, 'first_touch',
                   $4, $5, $6, $7, $8, $9, $10, $11::uuid, $12
            WHERE NOT EXISTS (
                SELECT 1 FROM analytics_touchpoints 
                WHERE anonymous_id = $1 AND touchpoint_type = 'first_touch'
            )
            ''',
            req.anonymous_id, req.user_id, req.workspace_id,
            req.referrer, req.utm_source, req.utm_medium, req.utm_campaign,
            req.utm_term, req.utm_content, req.landing_page, event_id, req.event_type,
        )
        
        # Update last-touch touchpoint
        await conn.execute(
            '''
            INSERT INTO analytics_touchpoints (
                anonymous_id, user_id, workspace_id, touchpoint_type,
                referrer, utm_source, utm_medium, utm_campaign, utm_term, utm_content,
                landing_page, event_id, event_type, touched_at
            )
            VALUES ($1, $2, $3, 'last_touch',
                    $4, $5, $6, $7, $8, $9, $10, $11::uuid, $12, NOW())
            ON CONFLICT (anonymous_id, touchpoint_type) DO UPDATE SET
                user_id = COALESCE(EXCLUDED.user_id, analytics_touchpoints.user_id),
                workspace_id = COALESCE(EXCLUDED.workspace_id, analytics_touchpoints.workspace_id),
                referrer = EXCLUDED.referrer,
                utm_source = EXCLUDED.utm_source,
                utm_medium = EXCLUDED.utm_medium,
                utm_campaign = EXCLUDED.utm_campaign,
                utm_term = EXCLUDED.utm_term,
                utm_content = EXCLUDED.utm_content,
                landing_page = EXCLUDED.landing_page,
                event_id = EXCLUDED.event_id,
                event_type = EXCLUDED.event_type,
                touched_at = NOW()
            ''',
            req.anonymous_id, req.user_id, req.workspace_id,
            req.referrer, req.utm_source, req.utm_medium, req.utm_campaign,
            req.utm_term, req.utm_content, req.landing_page, event_id, req.event_type,
        )
        
        # If this is a conversion event, queue it for ad platform forwarding
        if req.event_type in CONVERSION_EVENTS:
            email = req.properties.get('email')
            phone = req.properties.get('phone')
            
            await conn.execute(
                '''
                INSERT INTO analytics_conversions (
                    event_id, conversion_type, conversion_value, currency,
                    email, phone, user_id, workspace_id,
                    x_click_id, fb_click_id, google_click_id,
                    occurred_at
                ) VALUES (
                    $1::uuid, $2, $3, $4,
                    $5, $6, $7, $8,
                    $9, $10, $11,
                    $12
                )
                ''',
                event_id, req.event_type, req.conversion_value, req.currency,
                email, phone, req.user_id, req.workspace_id,
                req.x_click_id, req.fb_click_id, req.google_click_id,
                event_time,
            )
            
            # Also create conversion_touch touchpoint
            await conn.execute(
                '''
                INSERT INTO analytics_touchpoints (
                    anonymous_id, user_id, workspace_id, touchpoint_type,
                    referrer, utm_source, utm_medium, utm_campaign, utm_term, utm_content,
                    landing_page, event_id, event_type, touched_at
                )
                VALUES ($1, $2, $3, 'conversion_touch',
                        $4, $5, $6, $7, $8, $9, $10, $11::uuid, $12, NOW())
                ON CONFLICT (anonymous_id, touchpoint_type) DO UPDATE SET
                    user_id = COALESCE(EXCLUDED.user_id, analytics_touchpoints.user_id),
                    workspace_id = COALESCE(EXCLUDED.workspace_id, analytics_touchpoints.workspace_id),
                    referrer = EXCLUDED.referrer,
                    utm_source = EXCLUDED.utm_source,
                    utm_medium = EXCLUDED.utm_medium,
                    utm_campaign = EXCLUDED.utm_campaign,
                    utm_term = EXCLUDED.utm_term,
                    utm_content = EXCLUDED.utm_content,
                    landing_page = EXCLUDED.landing_page,
                    event_id = EXCLUDED.event_id,
                    event_type = EXCLUDED.event_type,
                    touched_at = NOW()
                ''',
                req.anonymous_id, req.user_id, req.workspace_id,
                req.referrer, req.utm_source, req.utm_medium, req.utm_campaign,
                req.utm_term, req.utm_content, req.landing_page, event_id, req.event_type,
            )
            
            logger.info(f'Conversion event queued: {req.event_type} for user {req.user_id}')
    
    return TrackEventResponse(
        success=True,
        event_id=event_id,
        message=f'Event {req.event_type} tracked',
    )


@router.post('/identify', response_model=IdentifyResponse)
async def identify_user(req: IdentifyRequest) -> IdentifyResponse:
    """
    Link an anonymous ID to a known user.
    
    Called when a user signs up or logs in to stitch their
    pre-signup activity to their account.
    """
    pool = await get_pool()
    if not pool:
        raise HTTPException(status_code=503, detail='Database unavailable')
    
    async with pool.acquire() as conn:
        await conn.execute(
            '''
            INSERT INTO analytics_identity_map (
                anonymous_id, user_id, workspace_id, email,
                user_linked_at, last_seen_at
            )
            VALUES ($1, $2, $3, $4, NOW(), NOW())
            ON CONFLICT (anonymous_id) DO UPDATE SET
                user_id = COALESCE(EXCLUDED.user_id, analytics_identity_map.user_id),
                workspace_id = COALESCE(EXCLUDED.workspace_id, analytics_identity_map.workspace_id),
                email = COALESCE(EXCLUDED.email, analytics_identity_map.email),
                user_linked_at = CASE 
                    WHEN EXCLUDED.user_id IS NOT NULL AND analytics_identity_map.user_id IS NULL 
                    THEN NOW() 
                    ELSE analytics_identity_map.user_linked_at 
                END,
                workspace_linked_at = CASE 
                    WHEN EXCLUDED.workspace_id IS NOT NULL AND analytics_identity_map.workspace_id IS NULL 
                    THEN NOW() 
                    ELSE analytics_identity_map.workspace_linked_at 
                END,
                last_seen_at = NOW()
            ''',
            req.anonymous_id, req.user_id, req.workspace_id, req.email,
        )
        
        # Backfill user_id on past events for this anonymous_id
        if req.user_id:
            await conn.execute(
                '''
                UPDATE analytics_events 
                SET user_id = $2
                WHERE anonymous_id = $1 AND user_id IS NULL
                ''',
                req.anonymous_id, req.user_id,
            )
        
        if req.workspace_id:
            await conn.execute(
                '''
                UPDATE analytics_events 
                SET workspace_id = $2
                WHERE anonymous_id = $1 AND workspace_id IS NULL
                ''',
                req.anonymous_id, req.workspace_id,
            )
    
    return IdentifyResponse(success=True, message='Identity linked')


@router.post('/page', response_model=TrackEventResponse)
async def track_page_view(
    req: PageViewRequest,
    request: Request,
) -> TrackEventResponse:
    """
    Convenience endpoint for tracking page views.
    
    Equivalent to calling /track with event_type='page_view'.
    """
    track_req = TrackEventRequest(
        event_type='page_view',
        anonymous_id=req.anonymous_id,
        user_id=req.user_id,
        session_id=req.session_id,
        page_url=req.page_url,
        page_title=req.page_title,
        referrer=req.referrer,
        utm_source=req.utm_source,
        utm_medium=req.utm_medium,
        utm_campaign=req.utm_campaign,
        utm_term=req.utm_term,
        utm_content=req.utm_content,
        landing_page=req.page_url,
        x_click_id=req.x_click_id,
        fb_click_id=req.fb_click_id,
        google_click_id=req.google_click_id,
    )
    return await track_event(track_req, request)


@router.get('/funnel', response_model=FunnelMetricsResponse)
async def get_funnel_metrics(
    funnel_id: str = 'default-signup-funnel',
    days: int = 7,
) -> FunnelMetricsResponse:
    """
    Get funnel conversion metrics.
    
    Analyzes how users progress through a defined funnel
    over the specified time period.
    """
    pool = await get_pool()
    if not pool:
        raise HTTPException(status_code=503, detail='Database unavailable')
    
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)
    
    async with pool.acquire() as conn:
        # Get funnel definition
        funnel = await conn.fetchrow(
            'SELECT name, steps, window_hours FROM analytics_funnels WHERE id = $1',
            funnel_id,
        )
        
        if not funnel:
            raise HTTPException(status_code=404, detail='Funnel not found')
        
        steps_def = json.loads(funnel['steps']) if isinstance(funnel['steps'], str) else funnel['steps']
        funnel_name = funnel['name']
        
        # Count users at each step
        step_results = []
        prev_count = 0
        first_count = 0
        
        for i, step in enumerate(steps_def):
            event_type = step['event_type']
            step_name = step.get('name', event_type)
            
            # Count unique anonymous_ids that did this event
            count = await conn.fetchval(
                '''
                SELECT COUNT(DISTINCT anonymous_id)
                FROM analytics_events
                WHERE event_type = $1
                  AND event_time >= $2
                  AND event_time <= $3
                ''',
                event_type, start_date, end_date,
            )
            
            count = count or 0
            
            if i == 0:
                first_count = count
                conversion_rate = 100.0
                overall_rate = 100.0
            else:
                conversion_rate = (count / prev_count * 100) if prev_count > 0 else 0
                overall_rate = (count / first_count * 100) if first_count > 0 else 0
            
            step_results.append(FunnelStep(
                step_name=step_name,
                event_type=event_type,
                count=count,
                conversion_rate=round(conversion_rate, 2),
                overall_rate=round(overall_rate, 2),
            ))
            
            prev_count = count
        
        # Overall conversion rate (last step / first step)
        total_entered = first_count
        total_converted = step_results[-1].count if step_results else 0
        overall_rate = (total_converted / total_entered * 100) if total_entered > 0 else 0
        
        return FunnelMetricsResponse(
            funnel_name=funnel_name,
            date_range_start=start_date,
            date_range_end=end_date,
            total_entered=total_entered,
            total_converted=total_converted,
            overall_conversion_rate=round(overall_rate, 2),
            steps=step_results,
        )


@router.get('/attribution/{user_id}', response_model=AttributionData)
async def get_attribution(user_id: str) -> AttributionData:
    """
    Get attribution data for a user.
    
    Returns first-touch, last-touch, and conversion-touch attribution.
    """
    pool = await get_pool()
    if not pool:
        raise HTTPException(status_code=503, detail='Database unavailable')
    
    async with pool.acquire() as conn:
        # Get touchpoints via identity map
        touchpoints = await conn.fetch(
            '''
            SELECT t.touchpoint_type, t.utm_source, t.utm_medium, t.utm_campaign, t.touched_at
            FROM analytics_touchpoints t
            JOIN analytics_identity_map im ON t.anonymous_id = im.anonymous_id
            WHERE im.user_id = $1
            ''',
            user_id,
        )
        
        result = AttributionData(user_id=user_id)
        
        for tp in touchpoints:
            if tp['touchpoint_type'] == 'first_touch':
                result.first_touch_source = tp['utm_source']
                result.first_touch_medium = tp['utm_medium']
                result.first_touch_campaign = tp['utm_campaign']
                result.first_touch_at = tp['touched_at']
            elif tp['touchpoint_type'] == 'last_touch':
                result.last_touch_source = tp['utm_source']
                result.last_touch_medium = tp['utm_medium']
                result.last_touch_campaign = tp['utm_campaign']
                result.last_touch_at = tp['touched_at']
            elif tp['touchpoint_type'] == 'conversion_touch':
                result.conversion_source = tp['utm_source']
                result.conversion_medium = tp['utm_medium']
                result.conversion_campaign = tp['utm_campaign']
                result.conversion_at = tp['touched_at']
        
        return result


@router.get('/pending-conversions')
async def get_pending_conversions(
    platform: str = 'x',
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Get conversions pending forwarding to an ad platform.
    
    Used by the conversion forwarder job.
    """
    pool = await get_pool()
    if not pool:
        raise HTTPException(status_code=503, detail='Database unavailable')
    
    column = f'{platform}_forwarded'
    
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f'''
            SELECT id, event_id, conversion_type, conversion_value, currency,
                   email, phone, user_id, workspace_id,
                   x_click_id, fb_click_id, google_click_id,
                   occurred_at
            FROM analytics_conversions
            WHERE {column} = FALSE
            ORDER BY occurred_at ASC
            LIMIT $1
            ''',
            limit,
        )
        
        return [dict(row) for row in rows]


@router.post('/mark-forwarded/{conversion_id}')
async def mark_conversion_forwarded(
    conversion_id: str,
    platform: str = 'x',
    response_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """
    Mark a conversion as forwarded to an ad platform.
    
    Called by the conversion forwarder after successful API call.
    """
    pool = await get_pool()
    if not pool:
        raise HTTPException(status_code=503, detail='Database unavailable')
    
    column = f'{platform}_forwarded'
    at_column = f'{platform}_forwarded_at'
    response_column = f'{platform}_response'
    
    async with pool.acquire() as conn:
        await conn.execute(
            f'''
            UPDATE analytics_conversions
            SET {column} = TRUE,
                {at_column} = NOW(),
                {response_column} = $2
            WHERE id = $1::uuid
            ''',
            conversion_id,
            json.dumps(response_data) if response_data else None,
        )
    
    return {'status': 'marked', 'conversion_id': conversion_id, 'platform': platform}
