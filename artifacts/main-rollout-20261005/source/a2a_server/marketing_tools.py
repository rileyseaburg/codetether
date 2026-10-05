"""
Spotless Bin Co MCP Tools

Exposes spotlessbinco marketing services through MCP, enabling agents
to access CreativeDirector, Campaigns, Automations, Audiences, and Analytics.

These tools bridge the A2A/MCP world to the spotlessbinco oRPC and Rust APIs.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)

# Configuration from environment
SPOTLESSBINCO_API_URL = os.environ.get(
    'SPOTLESSBINCO_API_URL', 'http://localhost:8081'
)
SPOTLESSBINCO_RUST_URL = os.environ.get(
    'SPOTLESSBINCO_RUST_URL', 'http://localhost:8080'
)

# Shared HTTP session
_session: Optional[aiohttp.ClientSession] = None


async def _get_session() -> aiohttp.ClientSession:
    """Get or create shared HTTP session."""
    global _session
    if _session is None or _session.closed:
        connector = aiohttp.TCPConnector(limit=50, limit_per_host=20)
        _session = aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=120),
            headers={'Content-Type': 'application/json'},
        )
    return _session


async def _call_api(
    method: str,
    url: str,
    data: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Make an API call to spotlessbinco."""
    session = await _get_session()
    try:
        async with session.request(method, url, json=data) as resp:
            text = await resp.text()
            if resp.status in (200, 201):
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return {'success': True, 'response': text}
            else:
                logger.error(f'API error {resp.status}: {text[:500]}')
                return {'error': text[:500], 'status': resp.status}
    except Exception as e:
        logger.error(f'API call failed: {e}')
        return {'error': str(e)}


async def _call_orpc(procedure: str, data: Dict) -> Dict[str, Any]:
    """Call an oRPC procedure on the spotlessbinco TypeScript API."""
    return await _call_api(
        method='POST',
        url=f'{SPOTLESSBINCO_API_URL}/orpc/{procedure}',
        data=data,
    )


async def _call_rust(
    endpoint: str, method: str = 'POST', data: Optional[Dict] = None
) -> Dict[str, Any]:
    """Call the spotlessbinco Rust API."""
    return await _call_api(
        method=method,
        url=f'{SPOTLESSBINCO_RUST_URL}{endpoint}',
        data=data,
    )


# =============================================================================
# CREATIVE DIRECTOR TOOLS
# =============================================================================


async def spotless_generate_creative(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate an ad creative image from winning ad copy using CreativeDirector.

    Uses Gemini for prompt engineering and Imagen-3.0 for image generation.
    Returns asset_id, image_url, and the AI-enhanced visual prompt.
    """
    concept = args.get('concept')
    aspect_ratio = args.get('aspect_ratio', '1:1')
    initiative_id = args.get('initiative_id')

    if not concept:
        return {'error': 'concept is required'}

    result = await _call_rust(
        '/api/creative-assets/generate',
        data={
            'concept': concept,
            'aspect_ratio': aspect_ratio,
            'initiative_id': initiative_id,
        },
    )

    return result


async def spotless_batch_generate_creatives(
    args: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Generate multiple ad creatives in batch from a list of concepts.

    More efficient than calling generate_creative multiple times.
    """
    concepts = args.get('concepts', [])
    aspect_ratio = args.get('aspect_ratio', '1:1')
    initiative_id = args.get('initiative_id')

    if not concepts:
        return {'error': 'concepts array is required'}

    result = await _call_rust(
        '/api/creative-assets/batch-generate',
        data={
            'concepts': concepts,
            'aspect_ratio': aspect_ratio,
            'initiative_id': initiative_id,
        },
    )

    return result


async def spotless_get_top_creatives(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get top performing creative assets ranked by performance score.

    Use this to find winning creatives that should be scaled.
    """
    limit = args.get('limit', 10)

    result = await _call_rust(
        f'/api/creative-assets/top-performers?limit={limit}', method='GET'
    )
    return result


async def spotless_analyze_creative_performance(
    args: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Analyze creative concept performance and get AI recommendations.

    Returns winning concepts, average performance, and recommendations
    for what types of creatives to generate more of.
    """
    result = await _call_rust(
        '/api/creative-assets/analyze-concepts', method='GET'
    )
    return result


# =============================================================================
# CAMPAIGN MANAGEMENT TOOLS
# =============================================================================


async def spotless_create_campaign(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a marketing campaign on one or more ad platforms.

    Supports Facebook, TikTok, and Google Ads. Uses the UnifiedCampaignManager
    to deploy to multiple platforms with a single call.
    """
    name = args.get('name')
    platforms = args.get('platforms', ['facebook'])
    objective = args.get('objective', 'CONVERSIONS')
    budget = args.get('budget', 100)
    budget_type = args.get('budget_type', 'daily')
    targeting = args.get('targeting', {})
    creative_asset_ids = args.get('creative_asset_ids', [])
    funnel_id = args.get('funnel_id')
    initiative_id = args.get('initiative_id')

    if not name:
        return {'error': 'name is required'}

    result = await _call_orpc(
        'campaigns/create',
        {
            'name': name,
            'platforms': platforms,
            'objective': objective,
            'budget': budget,
            'budgetType': budget_type,
            'targeting': targeting,
            'creativeAssetIds': creative_asset_ids,
            'funnelId': funnel_id,
            'initiativeId': initiative_id,
        },
    )

    return result


async def spotless_update_campaign_status(
    args: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Update a campaign's status (active, paused, archived).

    Use to pause underperforming campaigns or resume paused ones.
    """
    campaign_id = args.get('campaign_id')
    status = args.get('status')

    if not campaign_id or not status:
        return {'error': 'campaign_id and status are required'}

    result = await _call_orpc(
        'campaigns/updateStatus',
        {
            'id': campaign_id,
            'status': status,
        },
    )

    return result


async def spotless_update_campaign_budget(
    args: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Update a campaign's budget.

    Use to scale up successful campaigns or reduce spend on underperformers.
    """
    campaign_id = args.get('campaign_id')
    budget = args.get('budget')

    if not campaign_id or budget is None:
        return {'error': 'campaign_id and budget are required'}

    result = await _call_orpc(
        'campaigns/updateBudget',
        {
            'id': campaign_id,
            'budget': budget,
        },
    )

    return result


async def spotless_get_campaign_metrics(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get performance metrics for a specific campaign.

    Returns impressions, clicks, conversions, spend, CTR, CPC, ROAS, etc.
    """
    campaign_id = args.get('campaign_id')

    if not campaign_id:
        return {'error': 'campaign_id is required'}

    result = await _call_orpc('campaigns/getMetrics', {'id': campaign_id})
    return result


async def spotless_list_campaigns(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    List all campaigns, optionally filtered by status or initiative.
    """
    status = args.get('status')
    initiative_id = args.get('initiative_id')
    platform = args.get('platform')

    params = {}
    if status:
        params['status'] = status
    if initiative_id:
        params['initiativeId'] = initiative_id
    if platform:
        params['platform'] = platform

    result = await _call_orpc('campaigns/list', params)
    return result


# =============================================================================
# AUTOMATION TOOLS
# =============================================================================


async def spotless_create_automation(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create an automation workflow for email/SMS sequences.

    Automations can be triggered by form submissions, tags, purchases,
    or upsell declines. Steps include email, SMS, wait, conditions, and tags.
    """
    name = args.get('name')
    trigger_type = args.get('trigger_type', 'form_submit')
    trigger_config = args.get('trigger_config', {})
    steps = args.get('steps', [])
    auto_activate = args.get('auto_activate', True)

    if not name:
        return {'error': 'name is required'}

    # Build workflow nodes and edges
    nodes, edges = _build_automation_graph(trigger_type, trigger_config, steps)

    result = await _call_orpc(
        'automations/create',
        {
            'name': name,
            'nodes': nodes,
            'edges': edges,
        },
    )

    # Activate if requested
    if result.get('success') and auto_activate and result.get('id'):
        await _call_orpc(
            'automations/updateStatus',
            {
                'id': result['id'],
                'status': 'active',
            },
        )
        result['status'] = 'active'

    return result


def _build_automation_graph(
    trigger_type: str, trigger_config: Dict, steps: List
) -> tuple:
    """Build automation nodes and edges from step definitions."""
    nodes = []
    edges = []

    # Start node
    nodes.append(
        {
            'id': 'start-1',
            'type': 'trigger',
            'position': {'x': 100, 'y': 100},
            'data': {
                'type': 'start',
                'label': 'Start',
                'config': {'trigger': trigger_type, **trigger_config},
            },
        }
    )

    prev_node_id = 'start-1'
    y_pos = 200

    for i, step in enumerate(steps):
        node_id = f'node-{i + 1}'

        # Parse step type and config
        if isinstance(step, str):
            node_type, node_config, label = _parse_step_string(step)
        else:
            node_type = step.get('type', 'action')
            node_config = step.get('config', {})
            label = step.get('name', node_type)

        nodes.append(
            {
                'id': node_id,
                'type': 'action',
                'position': {'x': 100, 'y': y_pos},
                'data': {
                    'type': node_type,
                    'label': label,
                    'config': node_config,
                },
            }
        )

        edges.append(
            {
                'id': f'edge-{prev_node_id}-{node_id}',
                'source': prev_node_id,
                'target': node_id,
            }
        )

        prev_node_id = node_id
        y_pos += 100

    # End node
    nodes.append(
        {
            'id': 'end-1',
            'type': 'end',
            'position': {'x': 100, 'y': y_pos},
            'data': {'type': 'end', 'label': 'End', 'config': {}},
        }
    )
    edges.append(
        {
            'id': f'edge-{prev_node_id}-end-1',
            'source': prev_node_id,
            'target': 'end-1',
        }
    )

    return nodes, edges


def _parse_step_string(step: str) -> tuple:
    """Parse a step string like 'wait_2_days' or 'welcome_email'."""
    if step.startswith('wait_'):
        parts = step.split('_')
        duration = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
        unit = parts[2] if len(parts) > 2 else 'days'
        return 'wait', {'duration': duration, 'unit': unit}, step
    elif 'email' in step:
        return 'email', {'templateName': step}, step
    elif 'sms' in step:
        return 'sms', {'templateName': step}, step
    elif 'call' in step:
        return 'call', {}, step
    elif 'tag' in step:
        tag_name = step.replace('tag_', '').replace('_', ' ')
        return 'tag', {'tagName': tag_name}, step
    else:
        return 'action', {}, step


async def spotless_trigger_automation(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Manually trigger automations of a specific type.

    Useful for testing or triggering automations programmatically.
    """
    trigger_type = args.get('trigger_type')
    lead_id = args.get('lead_id')
    customer_id = args.get('customer_id')
    email = args.get('email')
    metadata = args.get('metadata', {})

    if not trigger_type:
        return {'error': 'trigger_type is required'}

    result = await _call_orpc(
        'automations/trigger',
        {
            'triggerType': trigger_type,
            'leadId': lead_id,
            'customerId': customer_id,
            'email': email,
            'metadata': metadata,
        },
    )

    return result


async def spotless_list_automations(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    List all automation workflows.
    """
    status = args.get('status')

    result = await _call_orpc(
        'automations/list', {'status': status} if status else {}
    )
    return result


async def spotless_update_automation_status(
    args: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Update an automation's status (draft, active, paused, archived).
    """
    automation_id = args.get('automation_id')
    status = args.get('status')

    if not automation_id or not status:
        return {'error': 'automation_id and status are required'}

    result = await _call_orpc(
        'automations/updateStatus',
        {
            'id': automation_id,
            'status': status,
        },
    )

    return result


# =============================================================================
# AUDIENCE TOOLS
# =============================================================================


async def spotless_create_geo_audience(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a geographic targeting audience by zip codes.

    Syncs to specified ad platforms (Facebook, TikTok, Google).
    """
    name = args.get('name')
    zip_codes = args.get('zip_codes', [])
    platforms = args.get('platforms', ['facebook', 'tiktok'])
    initiative_id = args.get('initiative_id')

    if not name or not zip_codes:
        return {'error': 'name and zip_codes are required'}

    result = await _call_orpc(
        'audiences/create',
        {
            'name': name,
            'type': 'geo',
            'initiativeId': initiative_id,
            'targeting': {'zipCodes': zip_codes},
            'platforms': platforms,
        },
    )

    return result


async def spotless_create_lookalike_audience(
    args: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Create a lookalike audience from existing customers.

    Sources: existing_customers, high_value_customers, recent_converters
    """
    name = args.get('name')
    source = args.get('source', 'existing_customers')
    lookalike_percent = args.get('lookalike_percent', 1)
    platforms = args.get('platforms', ['facebook', 'tiktok'])
    initiative_id = args.get('initiative_id')

    if not name:
        return {'error': 'name is required'}

    result = await _call_orpc(
        'audiences/createLookalike',
        {
            'name': name,
            'initiativeId': initiative_id,
            'sourceType': source,
            'lookalikePercent': lookalike_percent,
            'platforms': platforms,
        },
    )

    return result


async def spotless_create_custom_audience(
    args: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Create a custom audience from email/phone lists.

    For Customer Match on ad platforms.
    """
    name = args.get('name')
    emails = args.get('emails', [])
    phones = args.get('phones', [])
    platforms = args.get('platforms', ['facebook', 'tiktok', 'google'])
    initiative_id = args.get('initiative_id')

    if not name:
        return {'error': 'name is required'}
    if not emails and not phones:
        return {'error': 'emails or phones are required'}

    result = await _call_orpc(
        'audiences/createCustom',
        {
            'name': name,
            'initiativeId': initiative_id,
            'emails': emails,
            'phones': phones,
            'platforms': platforms,
        },
    )

    return result


async def spotless_get_trash_zone_zips(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get zip codes for specified trash zones.

    Useful for building geo audiences based on service areas.
    """
    zone_ids = args.get('zone_ids', [])

    if not zone_ids:
        return {'error': 'zone_ids array is required'}

    result = await _call_rust(
        f'/api/trash-zones/zip-codes?zones={",".join(map(str, zone_ids))}',
        method='GET',
    )
    return result


# =============================================================================
# ANALYTICS TOOLS
# =============================================================================


async def spotless_get_unified_metrics(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get unified marketing metrics aggregated across all ad platforms.

    Returns impressions, clicks, conversions, spend, CTR, CPC, CPM, ROAS.
    """
    start_date = args.get('start_date')
    end_date = args.get('end_date')
    initiative_id = args.get('initiative_id')

    if not start_date or not end_date:
        return {'error': 'start_date and end_date are required'}

    result = await _call_orpc(
        'analytics/getUnifiedMetrics',
        {
            'startDate': start_date,
            'endDate': end_date,
            'initiativeId': initiative_id,
        },
    )

    return result


async def spotless_get_roi_metrics(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get ROI metrics combining ad spend with revenue from Stripe.

    Returns total spend, total revenue, ROAS, and profit.
    """
    start_date = args.get('start_date')
    end_date = args.get('end_date')

    if not start_date or not end_date:
        return {'error': 'start_date and end_date are required'}

    result = await _call_orpc(
        'analytics/getROIMetrics',
        {
            'startDate': start_date,
            'endDate': end_date,
        },
    )

    return result


async def spotless_get_channel_performance(
    args: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Get performance metrics for a specific marketing channel.

    Channels: facebook, tiktok, google, email, sms, direct_mail
    """
    channel = args.get('channel')
    start_date = args.get('start_date')
    end_date = args.get('end_date')

    if not channel:
        return {'error': 'channel is required'}

    # Route to appropriate platform API
    if channel in ('facebook', 'tiktok', 'google'):
        result = await _call_orpc(
            f'{channel}/getMetrics',
            {
                'startDate': start_date,
                'endDate': end_date,
            },
        )
    else:
        result = await _call_orpc(
            'analytics/getChannelMetrics',
            {
                'channel': channel,
                'startDate': start_date,
                'endDate': end_date,
            },
        )

    return result


async def spotless_thompson_sample_budget(
    args: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Get optimal budget allocation using Thompson Sampling bandit algorithm.

    Returns allocation percentages per channel and decision type (explore/exploit).
    """
    channels = args.get('channels', ['meta_ads', 'tiktok_ads', 'door_hangers'])
    initiative_id = args.get('initiative_id')
    zip_code = args.get('zip_code')

    result = await _call_rust(
        '/api/ml/thompson-sample',
        data={
            'channels': channels,
            'initiative_id': initiative_id,
            'zip_code': zip_code,
        },
    )

    return result


async def spotless_get_conversion_attribution(
    args: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Get multi-touch attribution data for conversions.

    Shows the customer journey from first touch to conversion.
    """
    customer_id = args.get('customer_id')
    conversion_id = args.get('conversion_id')

    if not customer_id and not conversion_id:
        return {'error': 'customer_id or conversion_id is required'}

    params = {}
    if customer_id:
        params['customer_id'] = customer_id
    if conversion_id:
        params['conversion_id'] = conversion_id

    result = await _call_rust(
        '/api/attribution/chain', method='GET', data=params
    )
    return result


# =============================================================================
# PLATFORM-SPECIFIC TOOLS
# =============================================================================


async def spotless_sync_facebook_metrics(
    args: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Sync campaign metrics from Facebook Ads.

    Pulls latest impressions, clicks, spend, and conversions.
    """
    result = await _call_orpc('facebook/syncMetrics', {})
    return result


async def spotless_sync_tiktok_metrics(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sync campaign metrics from TikTok Ads.
    """
    result = await _call_orpc('tiktok/syncMetrics', {})
    return result


async def spotless_sync_google_metrics(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sync campaign metrics from Google Ads.
    """
    result = await _call_orpc('google/syncMetrics', {})
    return result


async def spotless_send_facebook_conversion(
    args: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Send a conversion event to Facebook CAPI.

    For server-side conversion tracking.
    """
    event_name = args.get('event_name', 'Purchase')
    email = args.get('email')
    phone = args.get('phone')
    value = args.get('value')
    currency = args.get('currency', 'USD')
    event_id = args.get('event_id')

    result = await _call_orpc(
        'facebook/sendConversion',
        {
            'eventName': event_name,
            'email': email,
            'phone': phone,
            'value': value,
            'currency': currency,
            'eventId': event_id,
        },
    )

    return result


async def spotless_send_tiktok_event(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Send an event to TikTok Events API.
    """
    event_name = args.get('event_name')
    email = args.get('email')
    phone = args.get('phone')
    value = args.get('value')
    event_id = args.get('event_id')

    result = await _call_orpc(
        'tiktok/sendEvent',
        {
            'eventName': event_name,
            'email': email,
            'phone': phone,
            'value': value,
            'eventId': event_id,
        },
    )

    return result


# =============================================================================
# TOOL DEFINITIONS FOR MCP REGISTRATION
# =============================================================================


def get_marketing_tools() -> List[Dict[str, Any]]:
    """
    Get the list of marketing MCP tool definitions.

    Returns tools formatted for MCP registration.
    """
    return [
        # Creative Director Tools
        {
            'name': 'spotless_generate_creative',
            'description': 'Generate an ad creative image from winning ad copy using Gemini Imagen. Returns asset_id, image_url, and enhanced visual prompt.',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'concept': {
                        'type': 'string',
                        'description': 'The ad copy or concept to visualize',
                    },
                    'aspect_ratio': {
                        'type': 'string',
                        'enum': ['1:1', '9:16', '16:9'],
                        'default': '1:1',
                        'description': 'Image aspect ratio (1:1 for feed, 9:16 for stories)',
                    },
                    'initiative_id': {
                        'type': 'string',
                        'description': 'Optional parent initiative ID',
                    },
                },
                'required': ['concept'],
            },
        },
        {
            'name': 'spotless_batch_generate_creatives',
            'description': 'Generate multiple ad creatives in batch from a list of concepts. More efficient than individual calls.',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'concepts': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': 'List of concepts to generate',
                    },
                    'aspect_ratio': {'type': 'string', 'default': '1:1'},
                    'initiative_id': {'type': 'string'},
                },
                'required': ['concepts'],
            },
        },
        {
            'name': 'spotless_get_top_creatives',
            'description': 'Get top performing creative assets ranked by performance score. Use to find winning creatives to scale.',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'limit': {
                        'type': 'integer',
                        'default': 10,
                        'description': 'Number of top creatives to return',
                    }
                },
            },
        },
        {
            'name': 'spotless_analyze_creative_performance',
            'description': 'Analyze creative concept performance and get AI recommendations for what to generate more of.',
            'inputSchema': {'type': 'object', 'properties': {}},
        },
        # Campaign Tools
        {
            'name': 'spotless_create_campaign',
            'description': 'Create a marketing campaign on Facebook, TikTok, or Google Ads. Supports multi-platform deployment.',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'name': {'type': 'string', 'description': 'Campaign name'},
                    'platforms': {
                        'type': 'array',
                        'items': {
                            'type': 'string',
                            'enum': ['facebook', 'tiktok', 'google'],
                        },
                        'default': ['facebook'],
                    },
                    'objective': {
                        'type': 'string',
                        'enum': [
                            'CONVERSIONS',
                            'TRAFFIC',
                            'AWARENESS',
                            'LEADS',
                        ],
                        'default': 'CONVERSIONS',
                    },
                    'budget': {
                        'type': 'number',
                        'description': 'Budget amount',
                        'default': 100,
                    },
                    'budget_type': {
                        'type': 'string',
                        'enum': ['daily', 'lifetime'],
                        'default': 'daily',
                    },
                    'targeting': {
                        'type': 'object',
                        'description': 'Audience targeting config',
                    },
                    'creative_asset_ids': {
                        'type': 'array',
                        'items': {'type': 'integer'},
                        'description': 'Creative asset IDs to use',
                    },
                    'funnel_id': {
                        'type': 'string',
                        'description': 'Funnel to link for attribution',
                    },
                    'initiative_id': {'type': 'string'},
                },
                'required': ['name'],
            },
        },
        {
            'name': 'spotless_update_campaign_status',
            'description': "Update a campaign's status (active, paused, archived). Use to pause underperformers.",
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'campaign_id': {
                        'type': 'string',
                        'description': 'Campaign ID',
                    },
                    'status': {
                        'type': 'string',
                        'enum': ['active', 'paused', 'archived'],
                    },
                },
                'required': ['campaign_id', 'status'],
            },
        },
        {
            'name': 'spotless_update_campaign_budget',
            'description': "Update a campaign's budget. Use to scale successful campaigns.",
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'campaign_id': {'type': 'string'},
                    'budget': {'type': 'number'},
                },
                'required': ['campaign_id', 'budget'],
            },
        },
        {
            'name': 'spotless_get_campaign_metrics',
            'description': 'Get performance metrics for a campaign: impressions, clicks, conversions, spend, CTR, CPC, ROAS.',
            'inputSchema': {
                'type': 'object',
                'properties': {'campaign_id': {'type': 'string'}},
                'required': ['campaign_id'],
            },
        },
        {
            'name': 'spotless_list_campaigns',
            'description': 'List all campaigns, optionally filtered by status, platform, or initiative.',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'status': {
                        'type': 'string',
                        'enum': ['active', 'paused', 'archived'],
                    },
                    'platform': {
                        'type': 'string',
                        'enum': ['facebook', 'tiktok', 'google'],
                    },
                    'initiative_id': {'type': 'string'},
                },
            },
        },
        # Automation Tools
        {
            'name': 'spotless_create_automation',
            'description': 'Create an email/SMS automation workflow. Triggered by form submissions, tags, purchases, or upsell declines.',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'name': {
                        'type': 'string',
                        'description': 'Automation name',
                    },
                    'trigger_type': {
                        'type': 'string',
                        'enum': [
                            'form_submit',
                            'tag_added',
                            'purchase',
                            'decline_upsell',
                        ],
                        'default': 'form_submit',
                    },
                    'trigger_config': {
                        'type': 'object',
                        'description': 'Trigger-specific config (e.g., formId, tagName)',
                    },
                    'steps': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': "Workflow steps like 'welcome_email', 'wait_2_days', 'follow_up_sms'",
                    },
                    'auto_activate': {'type': 'boolean', 'default': True},
                },
                'required': ['name'],
            },
        },
        {
            'name': 'spotless_trigger_automation',
            'description': 'Manually trigger automations of a specific type. Useful for testing.',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'trigger_type': {'type': 'string'},
                    'lead_id': {'type': 'integer'},
                    'customer_id': {'type': 'integer'},
                    'email': {'type': 'string'},
                    'metadata': {'type': 'object'},
                },
                'required': ['trigger_type'],
            },
        },
        {
            'name': 'spotless_list_automations',
            'description': 'List all automation workflows.',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'status': {
                        'type': 'string',
                        'enum': ['draft', 'active', 'paused', 'archived'],
                    }
                },
            },
        },
        {
            'name': 'spotless_update_automation_status',
            'description': "Update an automation's status (draft, active, paused, archived).",
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'automation_id': {'type': 'string'},
                    'status': {
                        'type': 'string',
                        'enum': ['draft', 'active', 'paused', 'archived'],
                    },
                },
                'required': ['automation_id', 'status'],
            },
        },
        # Audience Tools
        {
            'name': 'spotless_create_geo_audience',
            'description': 'Create a geographic targeting audience by zip codes. Syncs to ad platforms.',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'name': {'type': 'string'},
                    'zip_codes': {'type': 'array', 'items': {'type': 'string'}},
                    'platforms': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'default': ['facebook', 'tiktok'],
                    },
                    'initiative_id': {'type': 'string'},
                },
                'required': ['name', 'zip_codes'],
            },
        },
        {
            'name': 'spotless_create_lookalike_audience',
            'description': 'Create a lookalike audience from existing customers, high-value customers, or recent converters.',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'name': {'type': 'string'},
                    'source': {
                        'type': 'string',
                        'enum': [
                            'existing_customers',
                            'high_value_customers',
                            'recent_converters',
                        ],
                        'default': 'existing_customers',
                    },
                    'lookalike_percent': {
                        'type': 'integer',
                        'minimum': 1,
                        'maximum': 10,
                        'default': 1,
                        'description': '1-10, lower = more similar',
                    },
                    'platforms': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'default': ['facebook', 'tiktok'],
                    },
                    'initiative_id': {'type': 'string'},
                },
                'required': ['name'],
            },
        },
        {
            'name': 'spotless_create_custom_audience',
            'description': 'Create a custom audience from email/phone lists for Customer Match.',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'name': {'type': 'string'},
                    'emails': {'type': 'array', 'items': {'type': 'string'}},
                    'phones': {'type': 'array', 'items': {'type': 'string'}},
                    'platforms': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'default': ['facebook', 'tiktok', 'google'],
                    },
                    'initiative_id': {'type': 'string'},
                },
                'required': ['name'],
            },
        },
        {
            'name': 'spotless_get_trash_zone_zips',
            'description': 'Get zip codes for specified trash zones. Useful for building geo audiences.',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'zone_ids': {'type': 'array', 'items': {'type': 'string'}}
                },
                'required': ['zone_ids'],
            },
        },
        # Analytics Tools
        {
            'name': 'spotless_get_unified_metrics',
            'description': 'Get unified marketing metrics aggregated across all ad platforms. Returns impressions, clicks, conversions, spend, CTR, CPC, CPM, ROAS.',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'start_date': {
                        'type': 'string',
                        'description': 'ISO date string',
                    },
                    'end_date': {
                        'type': 'string',
                        'description': 'ISO date string',
                    },
                    'initiative_id': {'type': 'string'},
                },
                'required': ['start_date', 'end_date'],
            },
        },
        {
            'name': 'spotless_get_roi_metrics',
            'description': 'Get ROI metrics combining ad spend with revenue from Stripe. Returns ROAS and profit.',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'start_date': {'type': 'string'},
                    'end_date': {'type': 'string'},
                },
                'required': ['start_date', 'end_date'],
            },
        },
        {
            'name': 'spotless_get_channel_performance',
            'description': 'Get performance metrics for a specific marketing channel (facebook, tiktok, google, email, sms, direct_mail).',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'channel': {
                        'type': 'string',
                        'enum': [
                            'facebook',
                            'tiktok',
                            'google',
                            'email',
                            'sms',
                            'direct_mail',
                        ],
                    },
                    'start_date': {'type': 'string'},
                    'end_date': {'type': 'string'},
                },
                'required': ['channel'],
            },
        },
        {
            'name': 'spotless_thompson_sample_budget',
            'description': 'Get optimal budget allocation using Thompson Sampling bandit algorithm. Returns allocation per channel and explore/exploit decision.',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'channels': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'default': ['meta_ads', 'tiktok_ads', 'door_hangers'],
                    },
                    'initiative_id': {'type': 'string'},
                    'zip_code': {'type': 'string'},
                },
            },
        },
        {
            'name': 'spotless_get_conversion_attribution',
            'description': 'Get multi-touch attribution data showing customer journey from first touch to conversion.',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'customer_id': {'type': 'integer'},
                    'conversion_id': {'type': 'string'},
                },
            },
        },
        # Platform Sync Tools
        {
            'name': 'spotless_sync_facebook_metrics',
            'description': 'Sync latest campaign metrics from Facebook Ads.',
            'inputSchema': {'type': 'object', 'properties': {}},
        },
        {
            'name': 'spotless_sync_tiktok_metrics',
            'description': 'Sync latest campaign metrics from TikTok Ads.',
            'inputSchema': {'type': 'object', 'properties': {}},
        },
        {
            'name': 'spotless_sync_google_metrics',
            'description': 'Sync latest campaign metrics from Google Ads.',
            'inputSchema': {'type': 'object', 'properties': {}},
        },
        {
            'name': 'spotless_send_facebook_conversion',
            'description': 'Send a conversion event to Facebook CAPI for server-side tracking.',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'event_name': {'type': 'string', 'default': 'Purchase'},
                    'email': {'type': 'string'},
                    'phone': {'type': 'string'},
                    'value': {'type': 'number'},
                    'currency': {'type': 'string', 'default': 'USD'},
                    'event_id': {'type': 'string'},
                },
            },
        },
        {
            'name': 'spotless_send_tiktok_event',
            'description': 'Send an event to TikTok Events API.',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'event_name': {'type': 'string'},
                    'email': {'type': 'string'},
                    'phone': {'type': 'string'},
                    'value': {'type': 'number'},
                    'event_id': {'type': 'string'},
                },
                'required': ['event_name'],
            },
        },
    ]


# Tool handler mapping
MARKETING_TOOL_HANDLERS = {
    # Creative
    'spotless_generate_creative': spotless_generate_creative,
    'spotless_batch_generate_creatives': spotless_batch_generate_creatives,
    'spotless_get_top_creatives': spotless_get_top_creatives,
    'spotless_analyze_creative_performance': spotless_analyze_creative_performance,
    # Campaigns
    'spotless_create_campaign': spotless_create_campaign,
    'spotless_update_campaign_status': spotless_update_campaign_status,
    'spotless_update_campaign_budget': spotless_update_campaign_budget,
    'spotless_get_campaign_metrics': spotless_get_campaign_metrics,
    'spotless_list_campaigns': spotless_list_campaigns,
    # Automations
    'spotless_create_automation': spotless_create_automation,
    'spotless_trigger_automation': spotless_trigger_automation,
    'spotless_list_automations': spotless_list_automations,
    'spotless_update_automation_status': spotless_update_automation_status,
    # Audiences
    'spotless_create_geo_audience': spotless_create_geo_audience,
    'spotless_create_lookalike_audience': spotless_create_lookalike_audience,
    'spotless_create_custom_audience': spotless_create_custom_audience,
    'spotless_get_trash_zone_zips': spotless_get_trash_zone_zips,
    # Analytics
    'spotless_get_unified_metrics': spotless_get_unified_metrics,
    'spotless_get_roi_metrics': spotless_get_roi_metrics,
    'spotless_get_channel_performance': spotless_get_channel_performance,
    'spotless_thompson_sample_budget': spotless_thompson_sample_budget,
    'spotless_get_conversion_attribution': spotless_get_conversion_attribution,
    # Platform Sync
    'spotless_sync_facebook_metrics': spotless_sync_facebook_metrics,
    'spotless_sync_tiktok_metrics': spotless_sync_tiktok_metrics,
    'spotless_sync_google_metrics': spotless_sync_google_metrics,
    'spotless_send_facebook_conversion': spotless_send_facebook_conversion,
    'spotless_send_tiktok_event': spotless_send_tiktok_event,
}
