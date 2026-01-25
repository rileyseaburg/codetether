#!/usr/bin/env python3
"""
Screenshot Agent - Captures key CodeTether screenshots for video ads.

Run with:
  source .venv/bin/activate && python scripts/capture_screenshots.py

Spawns parallel agents to capture multiple pages simultaneously.
"""

import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from playwright.async_api import async_playwright, Page, Browser

# Output directory
OUTPUT_DIR = Path('assets/screenshots')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Base URL - change for local dev
BASE_URL = os.environ.get('CODETETHER_URL', 'https://codetether.run')


# ========================================
# Screenshot Configurations
# ========================================

SCREENSHOTS = [
    # Hero / Landing
    {
        'name': '01_hero_landing',
        'url': '/',
        'description': 'Landing page hero section',
        'viewport': {'width': 1920, 'height': 1080},
        'wait_for': 'h1',
        'delay': 1.0,
    },
    # Key Feature: File Delivery
    {
        'name': '02_file_delivery',
        'url': '/#features',
        'description': 'Real file output feature',
        'viewport': {'width': 1920, 'height': 1080},
        'scroll_to': 600,
        'delay': 0.5,
    },
    # Key Feature: RLM Demo
    {
        'name': '03_rlm_demo',
        'url': '/#rlm',
        'description': 'RLM processing demo',
        'viewport': {'width': 1920, 'height': 1080},
        'scroll_to': 1200,
        'delay': 0.5,
    },
    # Integrations (Zapier, n8n, Make)
    {
        'name': '04_integrations',
        'url': '/#integrations',
        'description': 'Zapier, n8n, Make integrations',
        'viewport': {'width': 1920, 'height': 1080},
        'scroll_to': 800,
        'delay': 0.5,
    },
    # Pricing
    {
        'name': '05_pricing',
        'url': '/pricing',
        'description': 'Pricing page with free tier',
        'viewport': {'width': 1920, 'height': 1080},
        'delay': 1.0,
    },
    # Mobile Hero (for Stories/Reels)
    {
        'name': '06_mobile_hero',
        'url': '/',
        'description': 'Mobile landing page',
        'viewport': {'width': 390, 'height': 844},  # iPhone 14 Pro
        'device_scale': 3,
        'delay': 1.0,
    },
    # Mobile Features
    {
        'name': '07_mobile_features',
        'url': '/#features',
        'description': 'Mobile features section',
        'viewport': {'width': 390, 'height': 844},
        'device_scale': 3,
        'scroll_to': 400,
        'delay': 0.5,
    },
]


# ========================================
# Screenshot Agent
# ========================================


class ScreenshotAgent:
    """Agent that captures a single screenshot."""

    def __init__(self, config: Dict[str, Any], browser: Browser):
        self.config = config
        self.browser = browser
        self.name = config['name']

    async def capture(self) -> str:
        """Capture the screenshot and return the file path."""
        config = self.config

        # Create context with viewport
        viewport = config.get('viewport', {'width': 1920, 'height': 1080})
        device_scale = config.get('device_scale', 2)

        context = await self.browser.new_context(
            viewport=viewport,
            device_scale_factor=device_scale,
        )

        page = await context.new_page()

        try:
            # Navigate
            url = f'{BASE_URL}{config["url"]}'
            print(f'  [{self.name}] Loading {url}')
            await page.goto(url, wait_until='networkidle', timeout=30000)

            # Wait for element if specified
            if 'wait_for' in config:
                await page.wait_for_selector(config['wait_for'], timeout=10000)

            # Scroll if specified
            if 'scroll_to' in config:
                await page.evaluate(
                    f'window.scrollTo(0, {config["scroll_to"]})'
                )

            # Delay for animations
            delay = config.get('delay', 0.5)
            await asyncio.sleep(delay)

            # Capture
            filename = OUTPUT_DIR / f'{self.name}.png'
            await page.screenshot(path=str(filename), full_page=False)

            print(f'  [{self.name}] ✓ Saved {filename}')
            return str(filename)

        except Exception as e:
            print(f'  [{self.name}] ✗ Error: {e}')
            return ''

        finally:
            await context.close()


# ========================================
# Agent Spawner
# ========================================


async def spawn_screenshot_agents(
    configs: List[Dict[str, Any]], max_parallel: int = 3
) -> List[str]:
    """
    Spawn multiple screenshot agents in parallel.

    Args:
        configs: List of screenshot configurations
        max_parallel: Max concurrent agents

    Returns:
        List of saved file paths
    """
    print(f'\n{"=" * 50}')
    print(f'Screenshot Agent Spawner')
    print(f'{"=" * 50}')
    print(f'Base URL: {BASE_URL}')
    print(f'Output: {OUTPUT_DIR}')
    print(f'Screenshots: {len(configs)}')
    print(f'Max parallel: {max_parallel}')
    print(f'{"=" * 50}\n')

    saved_files = []

    async with async_playwright() as p:
        # Launch browser once, share among agents
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--disable-gpu',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ],
        )

        print(f'Browser launched (Chromium)')
        print(f'\nCapturing screenshots...\n')

        # Process in batches
        for i in range(0, len(configs), max_parallel):
            batch = configs[i : i + max_parallel]
            batch_num = (i // max_parallel) + 1
            total_batches = (len(configs) + max_parallel - 1) // max_parallel

            print(f'Batch {batch_num}/{total_batches}:')

            # Create agents for this batch
            agents = [ScreenshotAgent(config, browser) for config in batch]

            # Run in parallel
            tasks = [agent.capture() for agent in agents]
            results = await asyncio.gather(*tasks)

            # Collect results
            for path in results:
                if path:
                    saved_files.append(path)

            print()

        await browser.close()

    return saved_files


# ========================================
# Main
# ========================================


async def main():
    """Main entry point."""
    start_time = datetime.now()

    # Capture all screenshots
    saved_files = await spawn_screenshot_agents(
        configs=SCREENSHOTS, max_parallel=3
    )

    # Summary
    elapsed = (datetime.now() - start_time).total_seconds()

    print(f'{"=" * 50}')
    print(f'COMPLETE')
    print(f'{"=" * 50}')
    print(f'Screenshots saved: {len(saved_files)}/{len(SCREENSHOTS)}')
    print(f'Time elapsed: {elapsed:.1f}s')
    print(f'Output directory: {OUTPUT_DIR}')
    print(f'\nFiles:')
    for f in saved_files:
        print(f'  - {f}')
    print(f'{"=" * 50}')

    # Return file list for Creatify upload
    return saved_files


if __name__ == '__main__':
    asyncio.run(main())
