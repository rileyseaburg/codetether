# Marketing Tools

CodeTether provides 27 MCP tools for marketing operations, enabling agents to manage campaigns, create content, build audiences, and analyze performance.

## Overview

Marketing tools are organized into 5 categories:

- **Creative** - Generate and analyze ad creatives
- **Campaigns** - Manage marketing campaigns
- **Automations** - Set up marketing automations
- **Audiences** - Build and manage target audiences
- **Analytics** - Track performance and ROI

## Configuration

Marketing tools require configuration of API endpoints:

| Variable | Description | Default |
|----------|-------------|---------|
| `MARKETING_API_URL` | Marketing API server URL | `http://localhost:8081` |
| `MARKETING_RUST_URL` | Marketing Rust backend URL | `http://localhost:8080` |

## Tool Categories

### Creative Tools

#### `generate_creative`

Generate an ad creative image from winning ad copy using Gemini Imagen.

**Parameters:**
- `concept` (string): Creative concept/description
- `brand_guidelines` (string): Brand style guidelines (optional)

**Returns:**
- `asset_id`: Generated creative ID
- `image_url`: URL to generated image
- `enhanced_prompt`: The visual prompt used

**Example:**
```json
{
  "concept": "Product launch for new AI platform",
  "brand_guidelines": "Bold, modern, tech-focused"
}
```

#### `batch_generate_creatives`

Generate multiple creatives from a list of concepts.

**Parameters:**
- `concepts` (array): List of creative concepts
- `brand_guidelines` (string): Brand style guidelines (optional)

**Returns:**
- `creatives`: Array of generated creatives

#### `get_top_creatives`

Retrieve the best-performing creatives.

**Parameters:**
- `limit` (integer): Number of top creatives to return (default: 10)

**Returns:**
- `creatives`: Array of top-performing creatives with metrics

#### `analyze_creative_performance`

Analyze performance metrics for a creative.

**Parameters:**
- `asset_id` (string): Creative asset ID

**Returns:**
- `metrics`: Click-through rate, conversions, cost, ROI

### Campaign Tools

#### `create_campaign`

Create a new marketing campaign.

**Parameters:**
- `name` (string): Campaign name
- `budget` (number): Campaign budget
- `channels` (array): Target channels (facebook, tiktok, google, email)

**Returns:**
- `campaign_id`: New campaign ID
- `status`: Campaign status

#### `update_campaign_status`

Update campaign status.

**Parameters:**
- `campaign_id` (string): Campaign ID
- `status` (string): New status (draft, active, paused, completed)

#### `update_campaign_budget`

Update campaign budget.

**Parameters:**
- `campaign_id` (string): Campaign ID
- `budget` (number): New budget amount

#### `get_campaign_metrics`

Get performance metrics for a campaign.

**Parameters:**
- `campaign_id` (string): Campaign ID

**Returns:**
- `metrics`: Impressions, clicks, conversions, spend, ROI

#### `list_campaigns`

List all campaigns.

**Parameters:**
- `status` (string): Filter by status (optional)

**Returns:**
- `campaigns`: Array of campaigns

### Automation Tools

#### `create_automation`

Create a marketing automation workflow.

**Parameters:**
- `name` (string): Automation name
- `trigger` (object): Trigger conditions
- `actions` (array): Actions to execute

**Example:**
```json
{
  "name": "Welcome email series",
  "trigger": {
    "event": "user_signup",
    "delay_hours": 0
  },
  "actions": [
    {
      "type": "send_email",
      "template": "welcome"
    },
    {
      "type": "wait",
      "days": 3
    },
    {
      "type": "send_email",
      "template": "followup"
    }
  ]
}
```

#### `trigger_automation`

Manually trigger an automation.

**Parameters:**
- `automation_id` (string): Automation ID
- `context` (object): Trigger context data

#### `list_automations`

List all automations.

**Returns:**
- `automations`: Array of automations

#### `update_automation_status`

Update automation status.

**Parameters:**
- `automation_id` (string): Automation ID
- `status` (string): New status (active, paused, disabled)

### Audience Tools

#### `create_geo_audience`

Create a geographic audience based on zip codes.

**Parameters:**
- `name` (string): Audience name
- `zip_codes` (array): List of zip codes

**Returns:**
- `audience_id`: New audience ID

#### `create_lookalike_audience`

Create a lookalike audience based on source audience.

**Parameters:**
- `source_audience_id` (string): Source audience ID
- `name` (string): Lookalike audience name
- `size` (string): Audience size (1%, 5%, 10%)

#### `create_custom_audience`

Create a custom audience from customer data.

**Parameters:**
- `name` (string): Audience name
- `emails` (array): Customer email addresses (optional)
- `phone_numbers` (array): Customer phone numbers (optional)

#### `get_trash_zone_zips`

Get zip codes for trash zone targeting.

**Returns:**
- `zip_codes`: Array of zip codes

### Analytics Tools

#### `get_unified_metrics`

Get unified metrics across all marketing channels.

**Parameters:**
- `date_range` (object): Date range (start, end)

**Returns:**
- `metrics`: Total impressions, clicks, conversions, spend, CTR, CPA, ROAS

#### `get_roi_metrics`

Calculate ROI metrics for campaigns.

**Parameters:**
- `campaign_ids` (array): List of campaign IDs (optional)

**Returns:**
- `metrics`: ROI, ROAS, LTV:CAC ratio

#### `get_channel_performance`

Get performance breakdown by channel.

**Parameters:**
- `date_range` (object): Date range

**Returns:**
- `channels`: Performance by channel (facebook, tiktok, google, email)

#### `thompson_sample_budget`

Optimize budget allocation using Thompson sampling.

**Parameters:**
- `total_budget` (number): Total budget to allocate
- `channels` (array): Available channels

**Returns:**
- `allocation`: Recommended budget per channel

#### `get_conversion_attribution`

Get conversion attribution data.

**Parameters:**
- `date_range` (object): Date range

**Returns:**
- `attribution`: Last-click, first-click, and multi-touch attribution

### Platform Sync Tools

#### `sync_facebook_metrics`

Sync metrics from Facebook Ads API.

#### `sync_tiktok_metrics`

Sync metrics from TikTok Ads API.

#### `sync_google_metrics`

Sync metrics from Google Ads API.

#### `send_facebook_conversion`

Send conversion event to Facebook.

**Parameters:**
- `event_name` (string): Event type (purchase, lead, signup)
- `email` (string): Customer email
- `phone` (string): Customer phone
- `value` (number): Conversion value
- `event_id` (string): Event ID

#### `send_tiktok_event`

Send conversion event to TikTok.

**Parameters:**
- Same as Facebook conversion

## Using Tools via MCP

### Discovery

```bash
# List all marketing tools
curl -X POST http://localhost:8000/mcp/tools/list

# Search for creative tools
curl -X POST http://localhost:8000/mcp/tools/search \
  -H "Content-Type: application/json" \
  -d '{"query": "creative"}'
```

### Execution

```bash
# Generate a creative
curl -X POST http://localhost:8000/mcp/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "name": "generate_creative",
    "arguments": {
      "concept": "Summer sale promotion",
      "brand_guidelines": "Vibrant, summer colors, fun"
    }
  }'
```

## Integration with Agents

### From Agent Worker

```python
from a2a_server.mcp_http_server import call_mcp_tool

# Generate creative
result = await call_mcp_tool(
    "generate_creative",
    {
        "concept": "Product launch",
        "brand_guidelines": "Tech-focused, minimal"
    }
)

# Create campaign
campaign = await call_mcp_tool(
    "create_campaign",
    {
        "name": "Q1 Promotion",
        "budget": 5000,
        "channels": ["facebook", "tiktok"]
    }
)
```

### From Marketing Coordinator

The [Marketing Coordinator](marketing-coordinator.md) automatically uses these tools when planning initiatives.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/mcp/tools/list` | GET | List available marketing tools |
| `/mcp/tools/search` | POST | Search tools by keyword |
| `/mcp/tools/call` | POST | Execute a marketing tool |
| `/mcp/tools/schema` | GET | Get tool schema |

## Troubleshooting

### Tools not available?

Check API connection:
```bash
curl http://localhost:8081/health
```

### Creative generation failing?

Verify Gemini Imagen API is configured:
```bash
kubectl logs deployment/marketing-api | grep "imagen"
```

### Metrics not syncing?

Trigger manual sync:
```bash
curl -X POST http://localhost:8000/v1/marketing/sync/facebook
```

## See Also

- [Marketing Coordinator](marketing-coordinator.md)
- [MCP Tools](mcp-tools.md)
- [Agent Worker](agent-worker.md)
