"""
Creative Skill - Generates ad creatives via CreativeDirector service.
"""

import logging
from typing import Any, Dict, Optional

from .base import BaseSkill

logger = logging.getLogger(__name__)


class CreativeSkill(BaseSkill):
    """
    Skill for generating ad creatives.

    Delegates to the CreativeDirector service in spotlessbinco
    which uses Gemini for prompt engineering and Imagen for image generation.
    """

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute creative generation task."""
        concept = task.get('concept') or task.get('description', '')
        aspect_ratio = task.get('aspect_ratio', '1:1')

        return await self.generate_creative(
            initiative_id=task.get('initiative_id'),
            concept=concept,
            aspect_ratio=aspect_ratio,
        )

    async def generate_creative(
        self,
        initiative_id: Optional[str],
        concept: str,
        aspect_ratio: str = '1:1',
    ) -> Dict[str, Any]:
        """
        Generate an ad creative from a concept.

        Args:
            initiative_id: Optional ID of the parent initiative
            concept: The winning ad copy or concept to visualize
            aspect_ratio: "1:1" for feed, "9:16" for stories

        Returns:
            Dict with asset_id, image_url, enhanced_prompt
        """
        logger.info(f'Generating creative for concept: {concept[:50]}...')

        # Call the CreativeDirector API (Rust backend)
        result = await self._call_spotlessbinco_api(
            method='POST',
            endpoint='/api/creative-assets/generate',
            data={
                'concept': concept,
                'aspect_ratio': aspect_ratio,
                'initiative_id': initiative_id,
            },
            use_rust=True,
        )

        if 'error' in result:
            logger.error(f'Creative generation failed: {result["error"]}')
            return {
                'success': False,
                'error': result['error'],
            }

        return {
            'success': True,
            'asset_id': result.get('asset_id'),
            'image_url': result.get('image_url'),
            'enhanced_prompt': result.get('enhanced_prompt'),
            'concept': concept,
        }

    async def batch_generate(
        self,
        initiative_id: str,
        concepts: list[str],
        aspect_ratio: str = '1:1',
    ) -> Dict[str, Any]:
        """
        Generate multiple creatives in batch.

        Args:
            initiative_id: ID of the parent initiative
            concepts: List of concepts to generate creatives for
            aspect_ratio: Aspect ratio for all images

        Returns:
            Dict with results for each concept
        """
        logger.info(f'Batch generating {len(concepts)} creatives...')

        result = await self._call_spotlessbinco_api(
            method='POST',
            endpoint='/api/creative-assets/batch-generate',
            data={
                'concepts': concepts,
                'aspect_ratio': aspect_ratio,
                'initiative_id': initiative_id,
            },
            use_rust=True,
        )

        return result

    async def get_top_performers(self, limit: int = 10) -> Dict[str, Any]:
        """Get top performing creative assets."""
        return await self._call_spotlessbinco_api(
            method='GET',
            endpoint=f'/api/creative-assets/top-performers?limit={limit}',
            use_rust=True,
        )

    async def update_performance(
        self,
        asset_id: int,
        performance_score: float,
        impressions: int,
        clicks: int,
        conversions: int,
    ) -> Dict[str, Any]:
        """Update performance metrics for a creative asset."""
        return await self._call_spotlessbinco_api(
            method='POST',
            endpoint='/api/creative-assets/update-performance',
            data={
                'asset_id': asset_id,
                'performance_score': performance_score,
                'impressions': impressions,
                'clicks': clicks,
                'conversions': conversions,
            },
            use_rust=True,
        )
