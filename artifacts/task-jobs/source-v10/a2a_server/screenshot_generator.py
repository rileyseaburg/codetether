"""
Automated Screenshot Generator for Video Ad Assets

Uses Playwright to capture high-quality screenshots of CodeTether UI
for use in Creatify video ads.
"""

import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

# Requires: pip install playwright && playwright install chromium


async def capture_screenshots(
    urls: List[dict],
    output_dir: str = 'assets/screenshots',
    viewport_width: int = 1920,
    viewport_height: int = 1080,
    device: Optional[str] = None,  # "iPhone 14 Pro Max", "iPad Pro"
) -> List[str]:
    """
    Capture screenshots from URLs.

    Args:
        urls: List of {"url": "...", "name": "...", "wait_for": "selector", "actions": [...]}
        output_dir: Directory to save screenshots
        viewport_width: Browser width
        viewport_height: Browser height
        device: Optional device emulation

    Returns:
        List of saved file paths
    """
    from playwright.async_api import async_playwright

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    saved_files = []

    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=True)

        # Device emulation or custom viewport
        if device:
            device_config = p.devices.get(device, {})
            context = await browser.new_context(**device_config)
        else:
            context = await browser.new_context(
                viewport={'width': viewport_width, 'height': viewport_height},
                device_scale_factor=2,  # Retina quality
            )

        page = await context.new_page()

        for item in urls:
            url = item['url']
            name = item.get('name', url.split('/')[-1] or 'home')
            wait_for = item.get('wait_for')
            actions = item.get('actions', [])

            print(f'Capturing: {name} ({url})')

            try:
                await page.goto(url, wait_until='networkidle')

                # Wait for specific element if specified
                if wait_for:
                    await page.wait_for_selector(wait_for, timeout=10000)

                # Execute actions (click, type, scroll, etc.)
                for action in actions:
                    action_type = action.get('type')
                    selector = action.get('selector')
                    value = action.get('value')

                    if action_type == 'click':
                        await page.click(selector)
                    elif action_type == 'type':
                        await page.fill(selector, value)
                    elif action_type == 'scroll':
                        await page.evaluate(f'window.scrollTo(0, {value})')
                    elif action_type == 'wait':
                        await asyncio.sleep(float(value))

                # Capture screenshot
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f'{output_dir}/{name}_{timestamp}.png'
                await page.screenshot(path=filename, full_page=False)
                saved_files.append(filename)
                print(f'  Saved: {filename}')

            except Exception as e:
                print(f'  Error capturing {name}: {e}')

        await browser.close()

    return saved_files


async def capture_codetether_assets():
    """Capture CodeTether-specific screenshots for video ads."""

    # Define pages and states to capture
    urls = [
        # Landing page hero
        {
            'url': 'https://codetether.io',
            'name': 'hero',
            'wait_for': 'h1',
        },
        # Dashboard (if publicly accessible demo)
        {
            'url': 'https://codetether.io/dashboard',
            'name': 'dashboard',
            'wait_for': '.task-list',
        },
        # Features section
        {
            'url': 'https://codetether.io#features',
            'name': 'features',
            'actions': [
                {'type': 'scroll', 'value': 600},
                {'type': 'wait', 'value': 0.5},
            ],
        },
        # Pricing
        {
            'url': 'https://codetether.io/pricing',
            'name': 'pricing',
        },
        # RLM demo section
        {
            'url': 'https://codetether.io#rlm-demo',
            'name': 'rlm_demo',
            'actions': [
                {'type': 'scroll', 'value': 1200},
            ],
        },
    ]

    # Desktop screenshots
    desktop_files = await capture_screenshots(
        urls=urls,
        output_dir='assets/screenshots/desktop',
        viewport_width=1920,
        viewport_height=1080,
    )

    # Mobile screenshots (for Stories/Reels)
    mobile_files = await capture_screenshots(
        urls=urls,
        output_dir='assets/screenshots/mobile',
        device='iPhone 14 Pro Max',
    )

    return {
        'desktop': desktop_files,
        'mobile': mobile_files,
    }


async def capture_demo_sequence(
    output_dir: str = 'assets/screenshots/demo_sequence',
) -> List[str]:
    """
    Capture a sequence of screenshots showing a task flow.
    Perfect for animated video ads.
    """
    from playwright.async_api import async_playwright

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    saved_files = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            device_scale_factor=2,
        )
        page = await context.new_page()

        # Sequence: Show task creation → processing → completion
        steps = [
            ('01_empty_state', 'https://codetether.io/dashboard', None),
            (
                '02_new_task_modal',
                'https://codetether.io/dashboard?modal=new',
                None,
            ),
            (
                '03_task_created',
                'https://codetether.io/dashboard?task=demo',
                None,
            ),
            (
                '04_task_running',
                'https://codetether.io/dashboard?task=demo&status=running',
                None,
            ),
            (
                '05_task_complete',
                'https://codetether.io/dashboard?task=demo&status=complete',
                None,
            ),
            (
                '06_file_output',
                'https://codetether.io/dashboard?task=demo&tab=output',
                None,
            ),
        ]

        for name, url, wait_selector in steps:
            try:
                await page.goto(url, wait_until='networkidle')
                if wait_selector:
                    await page.wait_for_selector(wait_selector)
                await asyncio.sleep(0.5)

                filename = f'{output_dir}/{name}.png'
                await page.screenshot(path=filename)
                saved_files.append(filename)
                print(f'Captured: {name}')
            except Exception as e:
                print(f'Error on {name}: {e}')

        await browser.close()

    return saved_files


# ========================================
# Alternative: Generate with AI
# ========================================


async def generate_ai_images(
    prompts: List[str],
    output_dir: str = 'assets/ai_generated',
    aspect_ratio: str = '16:9',
) -> List[str]:
    """
    Generate images using AI (requires separate API like DALL-E, Midjourney, etc.)
    """
    # This would integrate with image generation APIs
    # For now, return prompts for manual generation

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    prompts_file = f'{output_dir}/prompts.txt'
    with open(prompts_file, 'w') as f:
        for i, prompt in enumerate(prompts, 1):
            f.write(f'{i}. {prompt}\n\n')

    print(f'Saved {len(prompts)} prompts to {prompts_file}')
    print("\nUse these with Midjourney, DALL-E, or Creatify's AI generation:")
    for prompt in prompts[:3]:
        print(f'  - {prompt[:80]}...')

    return [prompts_file]


# Pre-defined prompts for CodeTether ads
CODETETHER_IMAGE_PROMPTS = [
    'Clean modern SaaS dashboard showing AI task completion progress bar at 87%, minimalist design, blue and white color scheme, professional software interface',
    'Split screen comparison: left side shows messy chat interface with copy-paste arrows, right side shows clean file download with CSV and PDF icons, modern flat design',
    "Email inbox notification showing 'Your report is ready' with PDF attachment icon, clean Gmail-style interface, warm professional lighting",
    'Zapier-style automation flow diagram connecting to file outputs (CSV, PDF, code), colorful node-based workflow, dark background',
    'Person walking away from laptop while progress bar runs in background, coffee cup nearby, sunlight through window, productivity concept',
    "Before/after: cluttered desk with papers vs clean desk with single laptop showing 'Task Complete', minimalist office photography",
    'MIT campus building with futuristic AI visualization overlay, academic authority concept, evening lighting',
    "Smartphone notification 'Lead scores ready - 500 contacts analyzed' with checkmark, iOS style, professional business context",
]


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == 'prompts':
        # Generate AI image prompts
        asyncio.run(generate_ai_images(CODETETHER_IMAGE_PROMPTS))
    else:
        # Capture screenshots
        asyncio.run(capture_codetether_assets())
