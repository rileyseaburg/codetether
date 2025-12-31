"""
Audience Skill - Builds and manages target audiences.
"""

import logging
from typing import Any, Dict, List, Optional

from .base import BaseSkill

logger = logging.getLogger(__name__)


class AudienceSkill(BaseSkill):
    """
    Skill for building and managing target audiences.

    Creates audiences for ad targeting including:
    - Geographic targeting (zip codes, trash zones)
    - Customer lookalikes
    - Custom audiences from lead lists
    - Retargeting audiences
    """

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute audience management task."""
        action = task.get('action', 'build')

        if action == 'build':
            return await self.build_audience(
                initiative_id=task.get('initiative_id'),
                config=task.get('config', {}),
            )
        elif action == 'sync':
            return await self.sync_audience(
                audience_id=task.get('audience_id'),
                platforms=task.get(
                    'platforms', ['facebook', 'tiktok', 'google']
                ),
            )
        elif action == 'estimate':
            return await self.estimate_size(
                config=task.get('config', {}),
            )
        else:
            return {'error': f'Unknown action: {action}'}

    async def build_audience(
        self,
        initiative_id: Optional[str],
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Build a target audience based on configuration.

        Args:
            initiative_id: Optional ID of the parent initiative
            config: Audience configuration including:
                - type: "geo", "lookalike", "custom", "retargeting"
                - name: Audience name
                - Additional type-specific config

        Returns:
            Dict with audience_id, estimated_size, platform_audience_ids
        """
        audience_type = config.get('type', 'geo')
        name = config.get('name', f'Audience {initiative_id}')

        logger.info(f'Building {audience_type} audience: {name}')

        if audience_type == 'geo':
            return await self._build_geo_audience(initiative_id, name, config)
        elif audience_type == 'lookalike':
            return await self._build_lookalike_audience(
                initiative_id, name, config
            )
        elif audience_type == 'custom':
            return await self._build_custom_audience(
                initiative_id, name, config
            )
        elif audience_type == 'retargeting':
            return await self._build_retargeting_audience(
                initiative_id, name, config
            )
        else:
            return {'error': f'Unknown audience type: {audience_type}'}

    async def _build_geo_audience(
        self,
        initiative_id: Optional[str],
        name: str,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build a geographic targeting audience."""
        zip_codes = config.get('zip_codes', [])
        radius_miles = config.get('radius_miles')
        trash_zones = config.get('trash_zones', [])

        # If trash zones specified, get their zip codes
        if trash_zones:
            zone_zips = await self._get_trash_zone_zips(trash_zones)
            zip_codes = list(set(zip_codes + zone_zips))

        # Create the audience in the system
        result = await self._call_orpc(
            'audiences/create',
            {
                'name': name,
                'type': 'geo',
                'initiativeId': initiative_id,
                'targeting': {
                    'zipCodes': zip_codes,
                    'radiusMiles': radius_miles,
                },
            },
        )

        if result.get('success'):
            # Sync to ad platforms
            await self.sync_audience(
                audience_id=result.get('id'),
                platforms=config.get('platforms', ['facebook', 'tiktok']),
            )

        return result

    async def _build_lookalike_audience(
        self,
        initiative_id: Optional[str],
        name: str,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build a lookalike audience from a source."""
        source = config.get('source', 'existing_customers')
        lookalike_percent = config.get(
            'lookalike_percent', 1
        )  # 1% = most similar

        # Get source audience
        if source == 'existing_customers':
            source_data = await self._get_customer_emails()
        elif source == 'high_value_customers':
            source_data = await self._get_high_value_customers()
        elif source == 'recent_converters':
            source_data = await self._get_recent_converters()
        else:
            source_data = {'emails': []}

        # Create lookalike on each platform
        result = await self._call_orpc(
            'audiences/createLookalike',
            {
                'name': name,
                'initiativeId': initiative_id,
                'sourceType': source,
                'sourceData': source_data,
                'lookalikePercent': lookalike_percent,
                'platforms': config.get('platforms', ['facebook', 'tiktok']),
            },
        )

        return result

    async def _build_custom_audience(
        self,
        initiative_id: Optional[str],
        name: str,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build a custom audience from a list."""
        emails = config.get('emails', [])
        phones = config.get('phones', [])
        lead_ids = config.get('lead_ids', [])

        # If lead_ids provided, fetch their contact info
        if lead_ids:
            lead_data = await self._get_lead_contact_info(lead_ids)
            emails.extend(lead_data.get('emails', []))
            phones.extend(lead_data.get('phones', []))

        result = await self._call_orpc(
            'audiences/createCustom',
            {
                'name': name,
                'initiativeId': initiative_id,
                'emails': list(set(emails)),
                'phones': list(set(phones)),
                'platforms': config.get(
                    'platforms', ['facebook', 'tiktok', 'google']
                ),
            },
        )

        return result

    async def _build_retargeting_audience(
        self,
        initiative_id: Optional[str],
        name: str,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build a retargeting audience from website visitors."""
        pixel_events = config.get('pixel_events', ['page_view'])
        lookback_days = config.get('lookback_days', 30)
        funnel_id = config.get('funnel_id')

        result = await self._call_orpc(
            'audiences/createRetargeting',
            {
                'name': name,
                'initiativeId': initiative_id,
                'pixelEvents': pixel_events,
                'lookbackDays': lookback_days,
                'funnelId': funnel_id,
                'platforms': config.get('platforms', ['facebook', 'tiktok']),
            },
        )

        return result

    async def sync_audience(
        self,
        audience_id: str,
        platforms: List[str],
    ) -> Dict[str, Any]:
        """Sync an audience to ad platforms."""
        logger.info(f'Syncing audience {audience_id} to: {platforms}')

        results = {}

        for platform in platforms:
            result = await self._call_orpc(
                f'audiences/syncTo{platform.capitalize()}',
                {'audienceId': audience_id},
            )
            results[platform] = result

        return {
            'success': all(r.get('success', False) for r in results.values()),
            'results': results,
        }

    async def estimate_size(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Estimate audience size for a configuration."""
        audience_type = config.get('type', 'geo')

        if audience_type == 'geo':
            zip_codes = config.get('zip_codes', [])
            # Estimate based on population data
            return await self._call_spotlessbinco_api(
                method='POST',
                endpoint='/api/geo/estimate-reach',
                data={'zipCodes': zip_codes},
                use_rust=True,
            )
        else:
            return {
                'estimated_size': None,
                'message': 'Size estimation not available for this audience type',
            }

    async def _get_trash_zone_zips(self, trash_zones: List[str]) -> List[str]:
        """Get zip codes for trash zones."""
        result = await self._call_spotlessbinco_api(
            method='GET',
            endpoint=f'/api/trash-zones/zip-codes?zones={",".join(trash_zones)}',
            use_rust=True,
        )
        return result.get('zip_codes', [])

    async def _get_customer_emails(self) -> Dict[str, Any]:
        """Get emails of existing customers."""
        result = await self._call_orpc(
            'customers/getEmails',
            {'status': 'active'},
        )
        return {'emails': result.get('emails', [])}

    async def _get_high_value_customers(self) -> Dict[str, Any]:
        """Get high-value customer data for lookalike."""
        result = await self._call_orpc(
            'customers/getHighValue',
            {'minLtv': 500},
        )
        return {'emails': result.get('emails', [])}

    async def _get_recent_converters(self, days: int = 30) -> Dict[str, Any]:
        """Get recent converters for lookalike."""
        result = await self._call_orpc(
            'customers/getRecentConverters',
            {'days': days},
        )
        return {'emails': result.get('emails', [])}

    async def _get_lead_contact_info(
        self, lead_ids: List[int]
    ) -> Dict[str, Any]:
        """Get contact info for leads."""
        result = await self._call_orpc(
            'leads/getContactInfo',
            {'leadIds': lead_ids},
        )
        return result
