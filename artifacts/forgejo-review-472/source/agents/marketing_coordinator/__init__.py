"""
Marketing Coordinator Agent

A strategic marketing orchestration agent that oversees and coordinates
marketing initiatives across the Spotless Bin Co platform.

This agent:
- Leads marketing initiatives with strategic planning
- Coordinates CreativeDirector for ad creative generation
- Manages campaigns across Facebook, TikTok, and Google Ads
- Orchestrates automation workflows
- Analyzes performance and adapts strategies

Uses Azure AI Foundry with Claude Opus 4.5 for reasoning.
"""

from .agent import MarketingCoordinatorAgent
from .initiatives import InitiativeManager, Initiative, InitiativeStatus

__all__ = [
    'MarketingCoordinatorAgent',
    'InitiativeManager',
    'Initiative',
    'InitiativeStatus',
]

__version__ = '0.1.0'
