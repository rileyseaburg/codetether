"""
Marketing Coordinator Skills

Each skill is a specialized capability that the Marketing Coordinator
can execute. Skills delegate to spotlessbinco services via API calls.
"""

from .creative import CreativeSkill
from .campaign import CampaignSkill
from .automation import AutomationSkill
from .analytics import AnalyticsSkill
from .audience import AudienceSkill

__all__ = [
    'CreativeSkill',
    'CampaignSkill',
    'AutomationSkill',
    'AnalyticsSkill',
    'AudienceSkill',
]
