# CodeTether Video Demo Pipeline

This document describes the end-to-end pipeline for generating marketing videos showcasing CodeTether features.

## Overview

The pipeline has three stages:
1. **Cypress E2E Tests** - Record real demos of features in action
2. **Video Assets** - Collect Cypress recordings and screenshots
3. **Creatify AI** - Generate polished marketing videos from assets

## Stage 1: Cypress Demo Tests

### Available Demo Tests

| Test File | Features Demonstrated |
|-----------|----------------------|
| `ralph-demo.cy.js` | Ralph autonomous loop, task queue, agent discovery |
| `session-messages.cy.js` | Session management, message history |
| `a2a-protocol.cy.js` | A2A protocol communication |

### Running Demo Tests

```bash
# Run all demo tests and record video
cd /home/riley/A2A-Server-MCP
CYPRESS_API_URL=https://api.codetether.run npx cypress run --spec "cypress/e2e/ralph-demo.cy.js"

# Run in headed mode for debugging
npx cypress open
```

### Output Locations

- **Videos**: `cypress/videos/*.mp4`
- **Screenshots**: `cypress/screenshots/*/`

### Configuration

Edit `cypress.config.js` to customize:
- `video: true` - Enable video recording
- `videoCompression: 32` - Compression quality (0-51, lower = better quality)
- `screenshotsFolder` - Screenshot output directory
- `videosFolder` - Video output directory

## Stage 2: Video Assets

After running Cypress tests, collect assets:

```bash
# Copy to assets folder
cp cypress/videos/*.mp4 assets/demo-videos/
cp -r cypress/screenshots/* assets/demo-screenshots/
```

### Asset Inventory

Current assets in `/home/riley/A2A-Server-MCP/assets/`:
- `video_result.json` - Creatify video generation result
- `screenshots/` - Product screenshots

## Stage 3: Creatify Video Generation

### API Credentials

```
API_ID: ecf12e8c-6ee5-45ba-9b57-9fb11705da6c
API_KEY: (stored securely)
Credits: 500 remaining (as of Jan 24, 2026)
```

### Quick Generation

```python
# Using the creatify_video.py module
from a2a_server.creatify_video import generate_video_ad

result = await generate_video_ad(
    url="https://codetether.run",
    aspect_ratio="9x16",  # Vertical for Stories/Reels
    script="Your custom script here",
    wait_for_completion=True
)

print(f"Video URL: {result.video_url}")
```

### Manual API Flow

1. **Create Link** (analyze URL):
```bash
POST https://api.creatify.ai/api/links/
{"url": "https://codetether.run"}
# Returns: {"id": "link-uuid", "link": {...}}
```

2. **Generate Video**:
```bash
POST https://api.creatify.ai/api/link_to_videos/
{
  "link": "link-uuid",  # Use outer ID, not link.id!
  "aspect_ratio": "9x16",
  "script": "Your script..."
}
# Returns: {"id": "video-uuid", "status": "pending"}
```

3. **Poll Status**:
```bash
GET https://api.creatify.ai/api/link_to_videos/{video-uuid}/
# When status="done": video_output contains URL
```

### Video Types

| Type | Aspect Ratio | Use Case |
|------|-------------|----------|
| `9x16` | 9:16 vertical | TikTok, Instagram Reels, Stories |
| `16x9` | 16:9 horizontal | YouTube, Facebook Feed |
| `1x1` | 1:1 square | Instagram Feed, Facebook |

### Script Templates

**Problem-Focused** (for pain point awareness):
```
Stop copy-pasting from ChatGPT into spreadsheets.
CodeTether delivers real files automatically.
Trigger a task via Zapier, walk away, get CSV, PDF, or code delivered by email.
Runs 5 to 60 minutes unattended.
Powered by MIT research.
Start free at CodeTether dot run.
```

**Result-Focused** (for solution seekers):
```
Get a 500-lead scoring spreadsheet delivered to your inbox.
Automatically.
CodeTether runs AI tasks in the background for 5 to 60 minutes.
Then delivers real files: CSV, PDF, code, reports.
No babysitting. No copy-pasting.
Start free at CodeTether dot run.
```

**Comparison** (vs ChatGPT):
```
ChatGPT is a chat.
CodeTether is a worker.
ChatGPT gives you text. You copy, paste, format.
CodeTether delivers real files. CSV. PDF. Code.
Trigger once via Zapier. Walk away.
Get deliverables by email.
```

## Complete Workflow

```bash
# 1. Run demo tests to record features
CYPRESS_API_URL=https://api.codetether.run \
  npx cypress run --spec "cypress/e2e/ralph-demo.cy.js"

# 2. Generate marketing video from recording
python3 << 'EOF'
import asyncio
from a2a_server.creatify_video import generate_codetether_video_ad

async def main():
    result = await generate_codetether_video_ad(
        script_style="problem_focused",
        aspect_ratio="9x16"
    )
    print(f"Video: {result.video_url}")

asyncio.run(main())
EOF

# 3. Download and review
curl -o demo-video.mp4 "VIDEO_URL_HERE"
```

## Costs

| Operation | Credits |
|-----------|---------|
| Create Link (URL analysis) | 1 |
| Generate Video (per 30s) | 5 |
| Generate Preview | 1 per 30s |
| Render from Preview | 4 per 30s |

## Latest Generated Video

- **Video ID**: `b9e77bcb-c39b-4093-ac5c-68fc4ccecaa7`
- **URL**: https://s3.us-west-2.amazonaws.com/remotionlambda-uswest2-30tewi8y5c/renders/kburgn4krd/output.mp4
- **Thumbnail**: https://dpbavq092lwjh.cloudfront.net/amzptv/c1f9dae5-801a-418d-8d9c-cefb7393be57-1769212114/thumbnail.jpg
- **Duration**: 24 seconds
- **Aspect Ratio**: 9:16 (vertical)
- **Credits Used**: 5

## Next Steps

1. Create more Cypress tests for other features:
   - Zapier integration demo
   - RLM large dataset processing
   - Multi-agent coordination

2. Record with authenticated user to show full dashboard

3. Create video variants:
   - Different scripts/angles
   - Multiple aspect ratios
   - A/B test different hooks
