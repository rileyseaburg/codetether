"""
Creatify AI Video Ad Generator Integration

Generates video ads from product URLs using Creatify's link_to_videos API.
Used for Facebook, TikTok, and other social media ad campaigns.

API Docs: https://docs.creatify.ai/api-reference/link_to_videos/post-apilink_to_videos
"""

import os
import logging
import httpx
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

# Creatify API Configuration
CREATIFY_API_BASE = 'https://api.creatify.ai/api'
CREATIFY_API_KEY = os.environ.get('CREATIFY_API_KEY')


class VideoStatus(str, Enum):
    """Creatify video generation status."""

    PENDING = 'pending'
    PROCESSING = 'processing'
    DONE = 'done'
    FAILED = 'failed'


@dataclass
class VideoAdRequest:
    """Request to generate a video ad from URL."""

    # Required
    url: str  # Product/landing page URL

    # Optional - Product Details
    product_name: Optional[str] = None
    product_description: Optional[str] = None

    # Optional - Video Settings
    aspect_ratio: str = (
        '9:16'  # 9:16 (vertical), 16:9 (horizontal), 1:1 (square)
    )
    duration: int = 30  # seconds
    language: str = 'en'

    # Optional - Branding
    logo_url: Optional[str] = None
    brand_color: Optional[str] = None

    # Optional - Voice/Avatar
    voice_id: Optional[str] = None
    avatar_id: Optional[str] = None

    # Optional - Script
    script: Optional[str] = None
    cta_text: Optional[str] = None


@dataclass
class VideoAdResult:
    """Result from video ad generation."""

    id: str
    status: VideoStatus
    video_url: Optional[str] = None
    preview_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    duration_seconds: Optional[int] = None
    credits_used: Optional[int] = None
    error: Optional[str] = None


class CreatifyClient:
    """Client for Creatify AI Video API."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or CREATIFY_API_KEY
        if not self.api_key:
            raise ValueError('CREATIFY_API_KEY environment variable not set')

        self.client = httpx.AsyncClient(
            base_url=CREATIFY_API_BASE,
            headers={
                'X-API-ID': self.api_key.split(':')[0]
                if ':' in self.api_key
                else self.api_key,
                'X-API-KEY': self.api_key.split(':')[1]
                if ':' in self.api_key
                else self.api_key,
                'Content-Type': 'application/json',
            },
            timeout=60.0,
        )

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

    # ========================================
    # Step 1: Create Link (analyze URL)
    # ========================================

    async def create_link(self, url: str) -> Dict[str, Any]:
        """
        Create a link from URL - analyzes the page and extracts product info.

        POST /links
        Cost: 1 credit

        Returns link_id to use for video generation.
        """
        response = await self.client.post('/links', json={'url': url})
        response.raise_for_status()
        return response.json()

    async def create_link_with_params(
        self,
        product_name: str,
        product_description: str,
        media_urls: List[str],
        logo_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a link with custom parameters (no URL scraping).

        POST /link_with_params
        Cost: 1 credit
        """
        data = {
            'product_name': product_name,
            'product_description': product_description,
            'media_urls': media_urls,
        }
        if logo_url:
            data['logo_url'] = logo_url

        response = await self.client.post('/link_with_params', json=data)
        response.raise_for_status()
        return response.json()

    # ========================================
    # Step 2: Generate Preview (optional)
    # ========================================

    async def generate_preview(
        self,
        link_id: str,
        aspect_ratio: str = '9:16',
        voice_id: Optional[str] = None,
        avatar_id: Optional[str] = None,
        script: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate a preview video before final render.

        POST /link_to_videos/preview
        Cost: 1 credit per 30 seconds
        """
        data = {
            'link_id': link_id,
            'aspect_ratio': aspect_ratio,
        }
        if voice_id:
            data['voice_id'] = voice_id
        if avatar_id:
            data['avatar_id'] = avatar_id
        if script:
            data['script'] = script

        response = await self.client.post('/link_to_videos/preview', json=data)
        response.raise_for_status()
        return response.json()

    async def generate_preview_list_async(
        self,
        link_id: str,
        aspect_ratio: str = '9:16',
        num_previews: int = 3,
    ) -> Dict[str, Any]:
        """
        Generate multiple preview variations asynchronously.

        POST /link_to_videos/preview_list_async
        Cost: 1 credit per 30 seconds per preview
        """
        response = await self.client.post(
            '/link_to_videos/preview_list_async',
            json={
                'link_id': link_id,
                'aspect_ratio': aspect_ratio,
                'num_previews': num_previews,
            },
        )
        response.raise_for_status()
        return response.json()

    # ========================================
    # Step 3: Render Final Video
    # ========================================

    async def create_video(
        self,
        link_id: str,
        aspect_ratio: str = '9:16',
        voice_id: Optional[str] = None,
        avatar_id: Optional[str] = None,
        script: Optional[str] = None,
        style: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create video directly from link (no preview).

        POST /link_to_videos
        Cost: 5 credits per 30 seconds
        """
        data = {
            'link_id': link_id,
            'aspect_ratio': aspect_ratio,
        }
        if voice_id:
            data['voice_id'] = voice_id
        if avatar_id:
            data['avatar_id'] = avatar_id
        if script:
            data['script'] = script
        if style:
            data['style'] = style

        response = await self.client.post('/link_to_videos', json=data)
        response.raise_for_status()
        return response.json()

    async def render_video(self, preview_id: str) -> Dict[str, Any]:
        """
        Render final video from preview.

        POST /link_to_videos/render
        Cost: 4 credits per 30 seconds
        """
        response = await self.client.post(
            '/link_to_videos/render', json={'preview_id': preview_id}
        )
        response.raise_for_status()
        return response.json()

    async def render_single_preview(
        self, preview_list_id: str, preview_index: int = 0
    ) -> Dict[str, Any]:
        """
        Render a specific preview from preview list.

        POST /link_to_videos/render_single_preview
        Cost: 4 credits per 30 seconds
        """
        response = await self.client.post(
            '/link_to_videos/render_single_preview',
            json={
                'preview_list_id': preview_list_id,
                'preview_index': preview_index,
            },
        )
        response.raise_for_status()
        return response.json()

    # ========================================
    # Step 4: Check Status / Get Result
    # ========================================

    async def get_video(self, video_id: str) -> Dict[str, Any]:
        """
        Get video status and result.

        GET /link_to_videos/{id}
        """
        response = await self.client.get(f'/link_to_videos/{video_id}')
        response.raise_for_status()
        return response.json()

    async def list_videos(
        self, ids: Optional[List[str]] = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        List video history.

        GET /link_to_videos
        """
        params: Dict[str, Any] = {'limit': limit}
        if ids:
            params['ids'] = ','.join(ids)

        response = await self.client.get('/link_to_videos', params=params)
        response.raise_for_status()
        return response.json()

    # ========================================
    # Utility: Get Available Assets
    # ========================================

    async def get_voices(self, language: str = 'en') -> List[Dict[str, Any]]:
        """Get available voice options."""
        response = await self.client.get(
            '/voices', params={'language': language}
        )
        response.raise_for_status()
        return response.json()

    async def get_avatars(self) -> List[Dict[str, Any]]:
        """Get available avatar options."""
        response = await self.client.get('/personas')
        response.raise_for_status()
        return response.json()

    async def get_remaining_credits(self) -> int:
        """Get remaining API credits."""
        response = await self.client.get('/workspace/remaining_credits')
        response.raise_for_status()
        data = response.json()
        return data.get('remaining_credits', 0)


# ========================================
# High-Level Functions
# ========================================


async def generate_video_ad(
    url: str,
    aspect_ratio: str = '9:16',
    voice_id: Optional[str] = None,
    avatar_id: Optional[str] = None,
    script: Optional[str] = None,
    wait_for_completion: bool = True,
    poll_interval: int = 10,
    max_wait: int = 300,
) -> VideoAdResult:
    """
    Generate a video ad from a product URL.

    Args:
        url: Product or landing page URL
        aspect_ratio: "9:16" (vertical), "16:9" (horizontal), "1:1" (square)
        voice_id: Optional voice ID for narration
        avatar_id: Optional avatar ID for presenter
        script: Optional custom script
        wait_for_completion: If True, poll until video is ready
        poll_interval: Seconds between status checks
        max_wait: Maximum seconds to wait

    Returns:
        VideoAdResult with video URL if successful

    Credit Cost:
        - 1 credit: Create link (URL analysis)
        - 5 credits per 30s: Video generation
    """
    import asyncio

    async with CreatifyClient() as client:
        # Step 1: Create link from URL
        logger.info(f'Creating link from URL: {url}')
        link_result = await client.create_link(url)
        link_id = link_result.get('id')

        if not link_id:
            return VideoAdResult(
                id='',
                status=VideoStatus.FAILED,
                error='Failed to create link from URL',
            )

        # Step 2: Generate video
        logger.info(f'Generating video for link: {link_id}')
        video_result = await client.create_video(
            link_id=link_id,
            aspect_ratio=aspect_ratio,
            voice_id=voice_id,
            avatar_id=avatar_id,
            script=script,
        )

        video_id = video_result.get('id')
        if not video_id:
            return VideoAdResult(
                id='', status=VideoStatus.FAILED, error='Failed to create video'
            )

        # Step 3: Poll for completion if requested
        if wait_for_completion:
            elapsed = 0
            while elapsed < max_wait:
                status_result = await client.get_video(video_id)
                status = status_result.get('status', 'pending')

                if status == 'done':
                    return VideoAdResult(
                        id=video_id,
                        status=VideoStatus.DONE,
                        video_url=status_result.get('video_url'),
                        preview_url=status_result.get('preview_url'),
                        thumbnail_url=status_result.get('thumbnail_url'),
                        duration_seconds=status_result.get('duration'),
                        credits_used=status_result.get('credits_used'),
                    )
                elif status == 'failed':
                    return VideoAdResult(
                        id=video_id,
                        status=VideoStatus.FAILED,
                        error=status_result.get(
                            'error', 'Video generation failed'
                        ),
                    )

                await asyncio.sleep(poll_interval)
                elapsed += poll_interval

            # Timeout
            return VideoAdResult(
                id=video_id,
                status=VideoStatus.PROCESSING,
                error=f'Video still processing after {max_wait}s',
            )

        # Return immediately without waiting
        return VideoAdResult(
            id=video_id,
            status=VideoStatus.PENDING,
        )


async def generate_video_ad_with_params(
    product_name: str,
    product_description: str,
    media_urls: List[str],
    logo_url: Optional[str] = None,
    aspect_ratio: str = '9:16',
    voice_id: Optional[str] = None,
    script: Optional[str] = None,
) -> VideoAdResult:
    """
    Generate a video ad from custom parameters (no URL scraping).

    Use this when you have product details directly instead of a URL.
    """
    async with CreatifyClient() as client:
        # Create link with params
        link_result = await client.create_link_with_params(
            product_name=product_name,
            product_description=product_description,
            media_urls=media_urls,
            logo_url=logo_url,
        )
        link_id = link_result.get('id')

        if not link_id:
            return VideoAdResult(
                id='',
                status=VideoStatus.FAILED,
                error='Failed to create link from params',
            )

        # Generate video
        video_result = await client.create_video(
            link_id=link_id,
            aspect_ratio=aspect_ratio,
            voice_id=voice_id,
            script=script,
        )

        return VideoAdResult(
            id=video_result.get('id', ''),
            status=VideoStatus.PENDING,
        )


# ========================================
# CodeTether Video Ad Generator
# ========================================

CODETETHER_AD_CONFIG = {
    'product_name': 'CodeTether - AI Tasks That Actually Finish',
    'product_description': """
AI automation that delivers real files, not just chat responses. 
Trigger once via Zapier, n8n, Make, or webhook - get CSV, PDF, code, and reports delivered by email.
Powered by MIT Recursive Language Model research that processes 10M+ tokens with 91% accuracy.
Run 5-60 minute tasks unattended while you focus on other work.
ChatGPT is a chat. CodeTether is a worker.
""".strip(),
    'url': 'https://codetether.io',
    'features': [
        'Delivers real files: CSV, PDF, code, reports',
        'Runs 5-60 minutes unattended',
        '10M+ token processing via RLM',
        'Works with Zapier, n8n, Make, webhooks',
        'Powered by MIT research',
    ],
    'cta': 'Start Free - 10 Tasks/Month',
    'scripts': {
        'problem_focused': """
Stop copy-pasting from ChatGPT into spreadsheets.
CodeTether delivers real files automatically.
Trigger a task, walk away, get CSV, PDF, or code delivered by email.
Works with Zapier, n8n, Make.
Powered by MIT research.
Start free at CodeTether.io
""".strip(),
        'result_focused': """
Get a 500-lead scoring spreadsheet delivered to your inbox.
Automatically.
CodeTether runs AI tasks in the background for 5 to 60 minutes.
Then delivers real files: CSV, PDF, code, reports.
No babysitting. No copy-pasting.
Works with Zapier, n8n, Make.
Start free at CodeTether.io
""".strip(),
        'comparison': """
ChatGPT is a chat.
CodeTether is a worker.
ChatGPT gives you text. You copy, paste, format.
CodeTether delivers real files. CSV. PDF. Code. Reports.
Trigger once via Zapier. Walk away.
Get deliverables by email.
Powered by MIT research.
Start free at CodeTether.io
""".strip(),
    },
}


async def generate_codetether_video_ad(
    script_style: str = 'problem_focused',
    aspect_ratio: str = '9:16',
) -> VideoAdResult:
    """
    Generate a CodeTether promotional video ad.

    Args:
        script_style: "problem_focused", "result_focused", or "comparison"
        aspect_ratio: "9:16" for vertical (Stories/Reels), "16:9" for horizontal
    """
    script = CODETETHER_AD_CONFIG['scripts'].get(script_style)

    return await generate_video_ad(
        url=CODETETHER_AD_CONFIG['url'],
        aspect_ratio=aspect_ratio,
        script=script,
        wait_for_completion=True,
    )
