"""
Analytics Skill - Analyzes marketing performance across channels.
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from .base import BaseSkill

logger = logging.getLogger(__name__)


class AnalyticsSkill(BaseSkill):
    """
    Skill for analyzing marketing performance.

    Aggregates metrics from Facebook, TikTok, Google Ads and provides
    unified analytics with insights and recommendations.
    """

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute analytics task."""
        action = task.get('action', 'report')

        if action == 'report':
            return await self.get_performance_report(
                initiative_id=task.get('initiative_id'),
                start_date=task.get('start_date'),
                end_date=task.get('end_date'),
            )
        elif action == 'insights':
            return await self.get_insights(
                initiative_id=task.get('initiative_id'),
            )
        elif action == 'reallocate':
            return await self.reallocate_budget(task)
        else:
            return {'error': f'Unknown action: {action}'}

    async def get_initiative_metrics(
        self, initiative_id: str
    ) -> Dict[str, Any]:
        """Get aggregated metrics for an initiative."""
        logger.info(f'Getting metrics for initiative: {initiative_id}')

        # Get unified metrics from the orchestrator
        result = await self._call_orpc(
            'analytics/getUnifiedMetrics',
            {
                'initiativeId': initiative_id,
                'startDate': (datetime.now() - timedelta(days=7)).isoformat(),
                'endDate': datetime.now().isoformat(),
            },
        )

        return result

    async def get_performance_report(
        self,
        initiative_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive performance report.

        Args:
            initiative_id: Optional initiative to filter by
            start_date: Start of reporting period (ISO format)
            end_date: End of reporting period (ISO format)

        Returns:
            Dict with aggregated metrics, platform breakdown, and trends
        """
        logger.info('Generating performance report...')

        # Default to last 7 days
        if not start_date:
            start_date = (datetime.now() - timedelta(days=7)).isoformat()
        if not end_date:
            end_date = datetime.now().isoformat()

        # Get metrics from all platforms
        unified = await self._call_orpc(
            'analytics/getUnifiedMetrics',
            {
                'startDate': start_date,
                'endDate': end_date,
                'initiativeId': initiative_id,
            },
        )

        # Get ROI metrics
        roi = await self._call_orpc(
            'analytics/getROIMetrics',
            {
                'startDate': start_date,
                'endDate': end_date,
            },
        )

        # Calculate key performance indicators
        kpis = self._calculate_kpis(unified, roi)

        return {
            'success': True,
            'period': {
                'start': start_date,
                'end': end_date,
            },
            'unified_metrics': unified,
            'roi_metrics': roi,
            'kpis': kpis,
            'generated_at': datetime.now().isoformat(),
        }

    def _calculate_kpis(
        self,
        unified: Dict[str, Any],
        roi: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Calculate key performance indicators from raw metrics."""
        total_spend = unified.get('totalSpend', 0)
        total_conversions = unified.get('totalConversions', 0)
        total_revenue = roi.get('totalRevenue', 0)

        return {
            'total_spend': total_spend,
            'total_conversions': total_conversions,
            'total_revenue': total_revenue,
            'cpa': total_spend / total_conversions
            if total_conversions > 0
            else None,
            'roas': total_revenue / total_spend if total_spend > 0 else None,
            'conversion_rate': unified.get('conversionRate'),
            'ctr': unified.get('ctr'),
            'cpm': unified.get('cpm'),
        }

    async def get_insights(
        self, initiative_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get AI-powered insights and recommendations.

        Args:
            initiative_id: Optional initiative to analyze

        Returns:
            Dict with insights, recommendations, and action items
        """
        logger.info('Generating insights...')

        # Get recent performance data
        report = await self.get_performance_report(initiative_id=initiative_id)

        insights = []
        recommendations = []

        kpis = report.get('kpis', {})

        # Analyze CPA
        cpa = kpis.get('cpa')
        if cpa is not None:
            if cpa > 75:
                insights.append(
                    {
                        'type': 'warning',
                        'metric': 'cpa',
                        'message': f'Cost per acquisition is high at ${cpa:.2f}',
                    }
                )
                recommendations.append(
                    {
                        'action': 'optimize_targeting',
                        'priority': 'high',
                        'message': 'Consider narrowing audience targeting to improve CPA',
                    }
                )
            elif cpa < 30:
                insights.append(
                    {
                        'type': 'success',
                        'metric': 'cpa',
                        'message': f'Excellent CPA at ${cpa:.2f}',
                    }
                )
                recommendations.append(
                    {
                        'action': 'scale_budget',
                        'priority': 'medium',
                        'message': 'Consider increasing budget to scale successful campaigns',
                    }
                )

        # Analyze ROAS
        roas = kpis.get('roas')
        if roas is not None:
            if roas < 2:
                insights.append(
                    {
                        'type': 'warning',
                        'metric': 'roas',
                        'message': f'ROAS is below target at {roas:.2f}x',
                    }
                )
                recommendations.append(
                    {
                        'action': 'pause_underperformers',
                        'priority': 'high',
                        'message': 'Pause campaigns with ROAS below 1.5x',
                    }
                )
            elif roas > 4:
                insights.append(
                    {
                        'type': 'success',
                        'metric': 'roas',
                        'message': f'Strong ROAS at {roas:.2f}x',
                    }
                )

        # Analyze CTR
        ctr = kpis.get('ctr')
        if ctr is not None and ctr < 1.0:
            insights.append(
                {
                    'type': 'warning',
                    'metric': 'ctr',
                    'message': f'Low click-through rate at {ctr:.2f}%',
                }
            )
            recommendations.append(
                {
                    'action': 'refresh_creatives',
                    'priority': 'medium',
                    'message': 'Generate new ad creatives to improve engagement',
                }
            )

        return {
            'success': True,
            'insights': insights,
            'recommendations': recommendations,
            'report': report,
        }

    async def reallocate_budget(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Reallocate budget based on Thompson Sampling optimization.

        Args:
            task: Task containing initiative_id or channel configuration

        Returns:
            Dict with new allocation and reasoning
        """
        logger.info('Reallocating budget via Thompson Sampling...')

        initiative_id = task.get('initiative_id')

        # Call the BulkAdsBandit to get optimal allocation
        result = await self._call_spotlessbinco_api(
            method='POST',
            endpoint='/api/ml/thompson-sample',
            data={
                'initiative_id': initiative_id,
                'channels': task.get(
                    'channels', ['meta_ads', 'tiktok_ads', 'door_hangers']
                ),
            },
            use_rust=True,
        )

        if 'error' in result:
            return result

        return {
            'success': True,
            'allocation': result.get('allocation', {}),
            'decision_type': result.get('decision_type'),  # explore vs exploit
            'reasoning': result.get('reasoning'),
        }

    async def get_channel_performance(
        self,
        channel: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get performance metrics for a specific channel."""
        if channel == 'facebook':
            return await self._call_orpc(
                'facebook/getMetrics',
                {
                    'startDate': start_date,
                    'endDate': end_date,
                },
            )
        elif channel == 'tiktok':
            return await self._call_orpc(
                'tiktok/getMetrics',
                {
                    'startDate': start_date,
                    'endDate': end_date,
                },
            )
        elif channel == 'google':
            return await self._call_orpc(
                'google/getMetrics',
                {
                    'startDate': start_date,
                    'endDate': end_date,
                },
            )
        else:
            return {'error': f'Unknown channel: {channel}'}

    async def get_conversion_attribution(
        self,
        conversion_id: Optional[str] = None,
        customer_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get attribution data for conversions."""
        return await self._call_spotlessbinco_api(
            method='GET',
            endpoint='/api/attribution/chain',
            data={
                'conversion_id': conversion_id,
                'customer_id': customer_id,
            },
            use_rust=True,
        )
