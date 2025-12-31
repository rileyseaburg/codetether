"""
MCP Tools for Spotless Bin Co Marketing Services

These tools expose spotlessbinco marketing capabilities through MCP,
allowing the Marketing Coordinator agent to access them via the
standard MCP tool interface.
"""

import json
import logging
import os
from typing import Any, Dict, Optional

import aiohttp

logger = logging.getLogger(__name__)

# Configuration from environment
SPOTLESSBINCO_API_URL = os.environ.get(
    'SPOTLESSBINCO_API_URL', 'http://localhost:8081'
)
SPOTLESSBINCO_RUST_URL = os.environ.get(
    'SPOTLESSBINCO_RUST_URL', 'http://localhost:8080'
)


async def _call_api(
    method: str,
    url: str,
    data: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Make an API call to spotlessbinco."""
    async with aiohttp.ClientSession() as session:
        async with session.request(method, url, json=data) as resp:
            if resp.status in (200, 201):
                return await resp.json()
            else:
                error = await resp.text()
                return {'error': error, 'status': resp.status}


async def _call_orpc(procedure: str, data: Dict) -> Dict[str, Any]:
    """Call an oRPC procedure."""
    return await _call_api(
        method='POST',
        url=f'{SPOTLESSBINCO_API_URL}/orpc/{procedure}',
        data=data,
    )


# =============================================================================
# Creative Director Tools
# =============================================================================


async def generate_creative(
    concept: str,
    aspect_ratio: str = '1:1',
    initiative_id: Optional[str] = None,
) -> str:
    """
    Generate an ad creative from a concept using CreativeDirector.

    Args:
        concept: The winning ad copy or concept to visualize
        aspect_ratio: "1:1" for feed posts, "9:16" for stories/reels
        initiative_id: Optional parent initiative ID

    Returns:
        JSON string with asset_id, image_url, enhanced_prompt
    """
    result = await _call_api(
        method='POST',
        url=f'{SPOTLESSBINCO_RUST_URL}/api/creative-assets/generate',
        data={
            'concept': concept,
            'aspect_ratio': aspect_ratio,
            'initiative_id': initiative_id,
        },
    )
    return json.dumps(result)


async def batch_generate_creatives(
    concepts: list,
    aspect_ratio: str = '1:1',
    initiative_id: Optional[str] = None,
) -> str:
    """
    Generate multiple ad creatives in batch.

    Args:
        concepts: List of concepts to generate creatives for
        aspect_ratio: Aspect ratio for all images
        initiative_id: Optional parent initiative ID

    Returns:
        JSON string with results for each concept
    """
    result = await _call_api(
        method='POST',
        url=f'{SPOTLESSBINCO_RUST_URL}/api/creative-assets/batch-generate',
        data={
            'concepts': concepts,
            'aspect_ratio': aspect_ratio,
            'initiative_id': initiative_id,
        },
    )
    return json.dumps(result)


async def get_top_performing_creatives(limit: int = 10) -> str:
    """
    Get top performing creative assets by performance score.

    Args:
        limit: Maximum number of assets to return

    Returns:
        JSON string with list of top performing assets
    """
    result = await _call_api(
        method='GET',
        url=f'{SPOTLESSBINCO_RUST_URL}/api/creative-assets/top-performers?limit={limit}',
    )
    return json.dumps(result)


# =============================================================================
# Campaign Management Tools
# =============================================================================


async def create_campaign(
    name: str,
    platforms: list,
    objective: str = 'CONVERSIONS',
    budget: float = 100,
    budget_type: str = 'daily',
    targeting: Optional[Dict] = None,
    creative_asset_ids: Optional[list] = None,
    initiative_id: Optional[str] = None,
) -> str:
    """
    Create a marketing campaign across one or more platforms.

    Args:
        name: Campaign name
        platforms: List of platforms ["facebook", "tiktok", "google"]
        objective: Marketing objective (CONVERSIONS, TRAFFIC, AWARENESS)
        budget: Daily or lifetime budget amount
        budget_type: "daily" or "lifetime"
        targeting: Audience targeting configuration
        creative_asset_ids: List of creative asset IDs to use
        initiative_id: Optional parent initiative ID

    Returns:
        JSON string with campaign_id and platform-specific IDs
    """
    result = await _call_orpc(
        'campaigns/create',
        {
            'name': name,
            'platforms': platforms,
            'objective': objective,
            'budget': budget,
            'budgetType': budget_type,
            'targeting': targeting or {},
            'creativeAssetIds': creative_asset_ids or [],
            'initiativeId': initiative_id,
        },
    )
    return json.dumps(result)


async def update_campaign_status(campaign_id: str, status: str) -> str:
    """
    Update a campaign's status.

    Args:
        campaign_id: The campaign ID
        status: New status ("active", "paused", "archived")

    Returns:
        JSON string with success status
    """
    result = await _call_orpc(
        'campaigns/updateStatus',
        {
            'id': campaign_id,
            'status': status,
        },
    )
    return json.dumps(result)


async def update_campaign_budget(campaign_id: str, budget: float) -> str:
    """
    Update a campaign's budget.

    Args:
        campaign_id: The campaign ID
        budget: New budget amount

    Returns:
        JSON string with success status
    """
    result = await _call_orpc(
        'campaigns/updateBudget',
        {
            'id': campaign_id,
            'budget': budget,
        },
    )
    return json.dumps(result)


async def get_campaign_metrics(campaign_id: str) -> str:
    """
    Get performance metrics for a campaign.

    Args:
        campaign_id: The campaign ID

    Returns:
        JSON string with impressions, clicks, conversions, spend, etc.
    """
    result = await _call_orpc('campaigns/getMetrics', {'id': campaign_id})
    return json.dumps(result)


# =============================================================================
# Automation Tools
# =============================================================================


async def create_automation(
    name: str,
    trigger_type: str,
    trigger_config: Optional[Dict] = None,
    steps: Optional[list] = None,
    auto_activate: bool = True,
) -> str:
    """
    Create an automation workflow.

    Args:
        name: Automation name
        trigger_type: Trigger type ("form_submit", "tag_added", "decline_upsell")
        trigger_config: Trigger-specific configuration
        steps: List of workflow steps (e.g., ["welcome_email", "wait_2_days", "follow_up_sms"])
        auto_activate: Whether to activate immediately

    Returns:
        JSON string with automation_id and status
    """
    # Build nodes and edges from steps
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
                'config': {
                    'trigger': trigger_type,
                    **(trigger_config or {}),
                },
            },
        }
    )

    prev_node_id = 'start-1'
    y_pos = 200

    for i, step in enumerate(steps or []):
        node_id = f'node-{i + 1}'
        node_type = _parse_step_type(step)

        nodes.append(
            {
                'id': node_id,
                'type': 'action',
                'position': {'x': 100, 'y': y_pos},
                'data': {
                    'type': node_type,
                    'label': step
                    if isinstance(step, str)
                    else step.get('name', node_type),
                    'config': _parse_step_config(step),
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

    # Create the automation
    result = await _call_orpc(
        'automations/create',
        {
            'name': name,
            'nodes': nodes,
            'edges': edges,
        },
    )

    # Activate if requested
    if result.get('success') and auto_activate:
        await _call_orpc(
            'automations/updateStatus',
            {
                'id': result.get('id'),
                'status': 'active',
            },
        )

    return json.dumps(result)


def _parse_step_type(step: Any) -> str:
    """Parse step type from step definition."""
    if isinstance(step, str):
        if step.startswith('wait'):
            return 'wait'
        elif 'email' in step:
            return 'email'
        elif 'sms' in step:
            return 'sms'
        elif 'call' in step:
            return 'call'
        elif 'mail' in step:
            return 'direct_mail'
        elif 'tag' in step:
            return 'tag'
    elif isinstance(step, dict):
        return step.get('type', 'action')
    return 'action'


def _parse_step_config(step: Any) -> Dict:
    """Parse step config from step definition."""
    if isinstance(step, str):
        if step.startswith('wait_'):
            parts = step.split('_')
            if len(parts) >= 3:
                duration = int(parts[1]) if parts[1].isdigit() else 1
                unit = parts[2]
                return {'duration': duration, 'unit': unit}
            return {'duration': 1, 'unit': 'days'}
        elif 'email' in step or 'sms' in step:
            return {'templateName': step}
    elif isinstance(step, dict):
        return step.get('config', step)
    return {}


async def trigger_automation(trigger_type: str, context: Dict) -> str:
    """
    Manually trigger automations of a specific type.

    Args:
        trigger_type: Type of trigger ("decline_upsell", "tag_added", etc.)
        context: Trigger context (leadId, customerId, email, etc.)

    Returns:
        JSON string with triggered count
    """
    result = await _call_orpc(
        'automations/trigger',
        {
            'triggerType': trigger_type,
            **context,
        },
    )
    return json.dumps(result)


async def list_automations(status: Optional[str] = None) -> str:
    """
    List all automations.

    Args:
        status: Optional filter by status ("draft", "active", "paused")

    Returns:
        JSON string with list of automations
    """
    result = await _call_orpc(
        'automations/list', {'status': status} if status else {}
    )
    return json.dumps(result)


# =============================================================================
# Audience Tools
# =============================================================================


async def create_geo_audience(
    name: str,
    zip_codes: list,
    platforms: Optional[list] = None,
    initiative_id: Optional[str] = None,
) -> str:
    """
    Create a geographic targeting audience.

    Args:
        name: Audience name
        zip_codes: List of zip codes to target
        platforms: Platforms to sync to ["facebook", "tiktok", "google"]
        initiative_id: Optional parent initiative ID

    Returns:
        JSON string with audience_id and platform IDs
    """
    result = await _call_orpc(
        'audiences/create',
        {
            'name': name,
            'type': 'geo',
            'initiativeId': initiative_id,
            'targeting': {'zipCodes': zip_codes},
        },
    )

    # Sync to platforms
    if result.get('success') and platforms:
        for platform in platforms:
            await _call_orpc(
                f'audiences/syncTo{platform.capitalize()}',
                {
                    'audienceId': result.get('id'),
                },
            )

    return json.dumps(result)


async def create_lookalike_audience(
    name: str,
    source: str = 'existing_customers',
    lookalike_percent: int = 1,
    platforms: Optional[list] = None,
    initiative_id: Optional[str] = None,
) -> str:
    """
    Create a lookalike audience from a source.

    Args:
        name: Audience name
        source: Source type ("existing_customers", "high_value_customers", "recent_converters")
        lookalike_percent: Similarity percentage (1-10, lower = more similar)
        platforms: Platforms to create on
        initiative_id: Optional parent initiative ID

    Returns:
        JSON string with audience_id and platform IDs
    """
    result = await _call_orpc(
        'audiences/createLookalike',
        {
            'name': name,
            'initiativeId': initiative_id,
            'sourceType': source,
            'lookalikePercent': lookalike_percent,
            'platforms': platforms or ['facebook', 'tiktok'],
        },
    )
    return json.dumps(result)


# =============================================================================
# Analytics Tools
# =============================================================================


async def get_unified_metrics(
    start_date: str,
    end_date: str,
    initiative_id: Optional[str] = None,
) -> str:
    """
    Get unified marketing metrics across all platforms.

    Args:
        start_date: Start date (ISO format)
        end_date: End date (ISO format)
        initiative_id: Optional initiative filter

    Returns:
        JSON string with aggregated metrics
    """
    result = await _call_orpc(
        'analytics/getUnifiedMetrics',
        {
            'startDate': start_date,
            'endDate': end_date,
            'initiativeId': initiative_id,
        },
    )
    return json.dumps(result)


async def get_roi_metrics(start_date: str, end_date: str) -> str:
    """
    Get ROI metrics combining ad spend with revenue.

    Args:
        start_date: Start date (ISO format)
        end_date: End date (ISO format)

    Returns:
        JSON string with ROAS, total spend, total revenue
    """
    result = await _call_orpc(
        'analytics/getROIMetrics',
        {
            'startDate': start_date,
            'endDate': end_date,
        },
    )
    return json.dumps(result)


async def thompson_sample_budget(
    channels: Optional[list] = None,
    initiative_id: Optional[str] = None,
) -> str:
    """
    Get optimal budget allocation using Thompson Sampling.

    Args:
        channels: Channels to allocate between (default: meta_ads, tiktok_ads, door_hangers)
        initiative_id: Optional initiative filter

    Returns:
        JSON string with allocation percentages and decision type (explore/exploit)
    """
    result = await _call_api(
        method='POST',
        url=f'{SPOTLESSBINCO_RUST_URL}/api/ml/thompson-sample',
        data={
            'initiative_id': initiative_id,
            'channels': channels or ['meta_ads', 'tiktok_ads', 'door_hangers'],
        },
    )
    return json.dumps(result)


# =============================================================================
# MCP Tool Registration
# =============================================================================


def get_mcp_tools() -> list:
    """
    Get the list of MCP tool definitions for registration.

    Returns:
        List of tool definitions in MCP format
    """
    return [
        {
            'name': 'spotless_generate_creative',
            'description': 'Generate an ad creative image from winning ad copy using Gemini Imagen',
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
                        'description': 'Image aspect ratio',
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
            'name': 'spotless_create_campaign',
            'description': 'Create a marketing campaign on Facebook, TikTok, or Google Ads',
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
                        'description': 'Platforms to deploy to',
                    },
                    'objective': {
                        'type': 'string',
                        'enum': ['CONVERSIONS', 'TRAFFIC', 'AWARENESS'],
                        'default': 'CONVERSIONS',
                    },
                    'budget': {
                        'type': 'number',
                        'description': 'Budget amount',
                    },
                    'budget_type': {
                        'type': 'string',
                        'enum': ['daily', 'lifetime'],
                        'default': 'daily',
                    },
                },
                'required': ['name', 'platforms'],
            },
        },
        {
            'name': 'spotless_create_automation',
            'description': 'Create an email/SMS automation workflow',
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
                            'decline_upsell',
                            'purchase',
                        ],
                        'description': 'What triggers this automation',
                    },
                    'steps': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': "Workflow steps like 'welcome_email', 'wait_2_days', 'follow_up_sms'",
                    },
                },
                'required': ['name', 'trigger_type'],
            },
        },
        {
            'name': 'spotless_create_geo_audience',
            'description': 'Create a geographic targeting audience by zip codes',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'name': {'type': 'string', 'description': 'Audience name'},
                    'zip_codes': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': 'Zip codes to target',
                    },
                    'platforms': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': 'Platforms to sync to',
                    },
                },
                'required': ['name', 'zip_codes'],
            },
        },
        {
            'name': 'spotless_get_metrics',
            'description': 'Get unified marketing metrics across all ad platforms',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'start_date': {
                        'type': 'string',
                        'description': 'Start date (ISO format)',
                    },
                    'end_date': {
                        'type': 'string',
                        'description': 'End date (ISO format)',
                    },
                    'initiative_id': {
                        'type': 'string',
                        'description': 'Optional initiative filter',
                    },
                },
                'required': ['start_date', 'end_date'],
            },
        },
        {
            'name': 'spotless_optimize_budget',
            'description': 'Get optimal budget allocation using Thompson Sampling bandit',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'channels': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': 'Marketing channels to allocate between',
                    },
                    'initiative_id': {
                        'type': 'string',
                        'description': 'Optional initiative filter',
                    },
                },
            },
        },
    ]


# Tool handler mapping for MCP server
TOOL_HANDLERS = {
    'spotless_generate_creative': generate_creative,
    'spotless_create_campaign': create_campaign,
    'spotless_create_automation': create_automation,
    'spotless_create_geo_audience': create_geo_audience,
    'spotless_get_metrics': get_unified_metrics,
    'spotless_optimize_budget': thompson_sample_budget,
}
