"""
Campaign Skill - Manages ad campaigns across platforms.
"""

import logging
from typing import Any, Dict, List, Optional

from .base import BaseSkill

logger = logging.getLogger(__name__)


class CampaignSkill(BaseSkill):
    """
    Skill for managing ad campaigns across Facebook, TikTok, and Google Ads.

    Delegates to the UnifiedCampaignManager and platform-specific adapters
    in the spotlessbinco API.
    """

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute campaign management task."""
        action = task.get('action', 'launch')

        if action == 'launch':
            return await self.launch_campaign(
                initiative_id=task.get('initiative_id'),
                platform=task.get('platform', 'facebook'),
                config=task.get('config', {}),
            )
        elif action == 'pause':
            return await self.pause_campaign(task.get('campaign_id'))
        elif action == 'resume':
            return await self.resume_campaign(task.get('campaign_id'))
        elif action == 'update_budget':
            return await self.update_budget(
                campaign_id=task.get('campaign_id'),
                budget=task.get('budget'),
            )
        else:
            return {'error': f'Unknown action: {action}'}

    async def launch_campaign(
        self,
        initiative_id: Optional[str],
        platform: str,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Launch a campaign on a specific platform.

        Args:
            initiative_id: Optional ID of the parent initiative
            platform: "facebook", "tiktok", or "google"
            config: Campaign configuration including:
                - name: Campaign name
                - objective: Marketing objective
                - budget: Daily or lifetime budget
                - targeting: Audience targeting config
                - creative_asset_ids: List of creative asset IDs to use

        Returns:
            Dict with campaign_id, platform_campaign_id, status
        """
        logger.info(f'Launching {platform} campaign...')

        # Call the unified campaign manager
        result = await self._call_orpc(
            'campaigns/create',
            {
                'platforms': [platform],
                'name': config.get('name', f'Initiative {initiative_id}'),
                'objective': config.get('objective', 'CONVERSIONS'),
                'budget': config.get('budget', 100),
                'budgetType': config.get('budget_type', 'daily'),
                'targeting': config.get('targeting', {}),
                'creativeAssetIds': config.get('creative_asset_ids', []),
                'initiativeId': initiative_id,
            },
        )

        if 'error' in result:
            logger.error(f'Campaign launch failed: {result["error"]}')
            return {
                'success': False,
                'error': result['error'],
            }

        return {
            'success': True,
            'campaign_id': result.get('id'),
            'platform_campaign_ids': result.get('platformCampaignIds', {}),
            'status': 'active',
        }

    async def launch_multi_platform(
        self,
        initiative_id: str,
        platforms: List[str],
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Launch campaigns across multiple platforms.

        Args:
            initiative_id: ID of the parent initiative
            platforms: List of platforms ["facebook", "tiktok", "google"]
            config: Campaign configuration

        Returns:
            Dict with results for each platform
        """
        logger.info(f'Launching multi-platform campaign on: {platforms}')

        result = await self._call_orpc(
            'campaigns/create',
            {
                'platforms': platforms,
                'name': config.get('name', f'Initiative {initiative_id}'),
                'objective': config.get('objective', 'CONVERSIONS'),
                'budget': config.get('budget', 100),
                'budgetType': config.get('budget_type', 'daily'),
                'targeting': config.get('targeting', {}),
                'creativeAssetIds': config.get('creative_asset_ids', []),
                'initiativeId': initiative_id,
            },
        )

        return result

    async def pause_campaign(self, campaign_id: str) -> Dict[str, Any]:
        """Pause a campaign."""
        logger.info(f'Pausing campaign: {campaign_id}')

        return await self._call_orpc(
            'campaigns/updateStatus',
            {
                'id': campaign_id,
                'status': 'paused',
            },
        )

    async def resume_campaign(self, campaign_id: str) -> Dict[str, Any]:
        """Resume a paused campaign."""
        logger.info(f'Resuming campaign: {campaign_id}')

        return await self._call_orpc(
            'campaigns/updateStatus',
            {
                'id': campaign_id,
                'status': 'active',
            },
        )

    async def update_budget(
        self,
        campaign_id: str,
        budget: float,
    ) -> Dict[str, Any]:
        """Update campaign budget."""
        logger.info(f'Updating budget for campaign {campaign_id}: ${budget}')

        return await self._call_orpc(
            'campaigns/updateBudget',
            {
                'id': campaign_id,
                'budget': budget,
            },
        )

    async def pause_underperformers(self, initiative_id: str) -> Dict[str, Any]:
        """Pause underperforming campaigns for an initiative."""
        logger.info(f'Pausing underperformers for initiative: {initiative_id}')

        # Get campaigns for this initiative
        campaigns = await self._call_orpc(
            'campaigns/listByInitiative',
            {'initiativeId': initiative_id},
        )

        paused = []
        for campaign in campaigns.get('campaigns', []):
            metrics = campaign.get('metrics', {})
            cpa = metrics.get('costPerAcquisition', float('inf'))

            # Pause if CPA is too high (2x average)
            if cpa > 100:  # Configurable threshold
                await self.pause_campaign(campaign['id'])
                paused.append(campaign['id'])

        return {
            'success': True,
            'paused_campaigns': paused,
            'count': len(paused),
        }

    async def trigger_budget_reallocation(
        self, initiative_id: str
    ) -> Dict[str, Any]:
        """Trigger budget reallocation based on Thompson Sampling."""
        logger.info(
            f'Triggering budget reallocation for initiative: {initiative_id}'
        )

        # Call the BulkAdsBandit to reallocate
        return await self._call_spotlessbinco_api(
            method='POST',
            endpoint='/api/ml/reallocate-budget',
            data={'initiative_id': initiative_id},
            use_rust=True,
        )

    async def get_campaign_metrics(self, campaign_id: str) -> Dict[str, Any]:
        """Get metrics for a specific campaign."""
        return await self._call_orpc(
            'campaigns/getMetrics',
            {'id': campaign_id},
        )

    async def sync_platform_metrics(self, platform: str) -> Dict[str, Any]:
        """Sync metrics from a specific ad platform."""
        return await self._call_orpc(
            f'{platform}/syncMetrics',
            {},
        )
