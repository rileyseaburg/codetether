#!/usr/bin/env python3
"""
Marketing Coordinator Agent

Strategic marketing orchestration agent that coordinates initiatives
by creating tasks for workers to execute via CodeTether.

Uses Azure AI Foundry with Claude Opus 4.5 for reasoning.
Delegates work to workers through the A2A task queue.
"""

import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp

from .initiatives import InitiativeManager, Initiative, InitiativeStatus

logger = logging.getLogger(__name__)


@dataclass
class MarketingCoordinatorConfig:
    """Configuration for the Marketing Coordinator Agent."""

    # A2A Server connection
    a2a_server_url: str = field(
        default_factory=lambda: os.environ.get(
            'A2A_SERVER_URL', 'http://localhost:8000'
        )
    )

    # Spotless Bin Co codebase ID (registered by worker)
    spotlessbinco_codebase_id: str = field(
        default_factory=lambda: os.environ.get(
            'SPOTLESSBINCO_CODEBASE_ID', 'spotlessbinco'
        )
    )

    # Azure AI Foundry / Claude configuration
    azure_endpoint: str = field(
        default_factory=lambda: os.environ.get('AZURE_AI_FOUNDRY_ENDPOINT', '')
    )
    azure_api_key: str = field(
        default_factory=lambda: os.environ.get('AZURE_AI_FOUNDRY_API_KEY', '')
    )
    model: str = field(
        default_factory=lambda: os.environ.get(
            'MARKETING_COORDINATOR_MODEL', 'claude-opus-4-5'
        )
    )

    # Agent identity
    agent_name: str = 'Marketing Coordinator'
    agent_id: str = field(
        default_factory=lambda: f'marketing-coordinator-{uuid.uuid4().hex[:8]}'
    )

    # Database for initiatives
    database_url: str = field(
        default_factory=lambda: os.environ.get('DATABASE_URL', '')
    )

    # Polling interval
    poll_interval: int = 10

    # Task timeout
    task_timeout: int = 300  # 5 minutes


class MarketingCoordinatorAgent:
    """
    Strategic marketing orchestration agent.

    This agent:
    1. Registers with the A2A server
    2. Listens for marketing-related tasks
    3. Plans marketing initiatives using AI
    4. Creates tasks for workers to execute marketing operations
    5. Monitors task completion and adapts strategies
    """

    # Agent card definition for A2A registration
    AGENT_CARD = {
        'name': 'Marketing Coordinator',
        'description': 'Strategic marketing orchestration agent for Spotless Bin Co. '
        'Plans initiatives, creates tasks for workers to execute marketing '
        'operations like generating creatives, launching campaigns, and '
        'building audiences.',
        'provider': {
            'organization': 'Spotless Bin Co',
            'url': 'https://spotlessbinco.com',
        },
        'capabilities': {
            'streaming': True,
            'push_notifications': True,
        },
        'skills': [
            {
                'id': 'plan-initiative',
                'name': 'Plan Marketing Initiative',
                'description': 'Creates a strategic marketing plan with tasks for workers to execute.',
            },
            {
                'id': 'coordinate-campaign',
                'name': 'Coordinate Campaign Launch',
                'description': 'Coordinates multi-platform campaign launch via worker tasks.',
            },
            {
                'id': 'analyze-and-optimize',
                'name': 'Analyze and Optimize',
                'description': 'Analyzes performance and creates optimization tasks.',
            },
        ],
        'version': '1.0',
    }

    def __init__(self, config: Optional[MarketingCoordinatorConfig] = None):
        self.config = config or MarketingCoordinatorConfig()
        self.session: Optional[aiohttp.ClientSession] = None
        self.running = False

        # Initialize initiative manager
        self.initiative_manager = InitiativeManager(self.config.database_url)

        # Track tasks we've created
        self.pending_tasks: Dict[str, Dict[str, Any]] = {}

        logger.info(
            f'Marketing Coordinator Agent initialized: {self.config.agent_id}'
        )

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self.session is None or self.session.closed:
            connector = aiohttp.TCPConnector(limit=50, limit_per_host=20)
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=60),
                headers={'Content-Type': 'application/json'},
            )
        return self.session

    # =========================================================================
    # A2A TASK MANAGEMENT
    # =========================================================================

    async def create_task(
        self,
        title: str,
        prompt: str,
        agent_type: str = 'build',
        codebase_id: Optional[str] = None,
        priority: int = 0,
        model: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Create a task for a worker to execute.

        Args:
            title: Task title
            prompt: The prompt/instructions for the worker (executed via CodeTether)
            agent_type: Type of agent (build, plan, general, explore)
            codebase_id: Target codebase (defaults to spotlessbinco)
            priority: Task priority (higher = more urgent)
            model: Model to use (defaults to claude-sonnet)

        Returns:
            Task details including task_id
        """
        session = await self._get_session()

        payload = {
            'title': title,
            'prompt': prompt,
            'agent_type': agent_type,
            'codebase_id': codebase_id or self.config.spotlessbinco_codebase_id,
            'priority': priority,
            'model': model or 'claude-sonnet',
        }

        try:
            async with session.post(
                f'{self.config.a2a_server_url}/v1/agent/tasks',
                json=payload,
            ) as resp:
                if resp.status in (200, 201):
                    task = await resp.json()
                    task_id = task.get('id')
                    logger.info(f'Created task {task_id}: {title}')

                    # Track the task
                    self.pending_tasks[task_id] = {
                        'task': task,
                        'created_at': datetime.now(),
                        'status': 'pending',
                    }

                    return task
                else:
                    error = await resp.text()
                    logger.error(
                        f'Failed to create task: {resp.status} - {error}'
                    )
                    return None
        except Exception as e:
            logger.error(f'Error creating task: {e}')
            return None

    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get the current status of a task."""
        session = await self._get_session()

        try:
            async with session.get(
                f'{self.config.a2a_server_url}/v1/agent/tasks/{task_id}',
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                return None
        except Exception as e:
            logger.error(f'Error getting task status: {e}')
            return None

    async def wait_for_task(
        self,
        task_id: str,
        timeout: Optional[int] = None,
        poll_interval: int = 5,
    ) -> Optional[Dict[str, Any]]:
        """
        Wait for a task to complete.

        Args:
            task_id: The task ID to wait for
            timeout: Maximum time to wait (seconds)
            poll_interval: How often to check (seconds)

        Returns:
            Final task state or None if timeout
        """
        timeout = timeout or self.config.task_timeout
        start_time = datetime.now()

        while True:
            task = await self.get_task_status(task_id)

            if task:
                status = task.get('status')

                if status in ('completed', 'failed', 'cancelled'):
                    # Update our tracking
                    if task_id in self.pending_tasks:
                        self.pending_tasks[task_id]['status'] = status
                        self.pending_tasks[task_id]['result'] = task.get(
                            'result'
                        )

                    return task

            # Check timeout
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed > timeout:
                logger.warning(f'Task {task_id} timed out after {timeout}s')
                return None

            await asyncio.sleep(poll_interval)

    # =========================================================================
    # MARKETING TASK BUILDERS
    # =========================================================================

    async def task_generate_creative(
        self,
        concept: str,
        aspect_ratio: str = '1:1',
        initiative_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Create a task to generate an ad creative.

        The worker will execute this via CodeTether, which will call the
        spotless_generate_creative MCP tool.
        """
        prompt = f"""Use the spotless_generate_creative MCP tool to generate an ad creative.

Concept: {concept}
Aspect Ratio: {aspect_ratio}
Initiative ID: {initiative_id or 'N/A'}

Call the tool and return the result including asset_id and image_url."""

        return await self.create_task(
            title=f'Generate Creative: {concept[:50]}...',
            prompt=prompt,
            agent_type='build',
            priority=5,
        )

    async def task_create_campaign(
        self,
        name: str,
        platforms: List[str],
        budget: float,
        targeting: Optional[Dict] = None,
        creative_asset_ids: Optional[List[int]] = None,
        initiative_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Create a task to launch a marketing campaign.
        """
        prompt = f"""Use the spotless_create_campaign MCP tool to create a marketing campaign.

Campaign Name: {name}
Platforms: {', '.join(platforms)}
Budget: ${budget}
Targeting: {json.dumps(targeting or {})}
Creative Asset IDs: {creative_asset_ids or []}
Initiative ID: {initiative_id or 'N/A'}

Call the tool with these parameters and return the campaign_id and platform IDs."""

        return await self.create_task(
            title=f'Launch Campaign: {name}',
            prompt=prompt,
            agent_type='build',
            priority=5,
        )

    async def task_create_automation(
        self,
        name: str,
        trigger_type: str,
        steps: List[str],
        trigger_config: Optional[Dict] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Create a task to set up an automation workflow.
        """
        prompt = f"""Use the spotless_create_automation MCP tool to create an automation workflow.

Automation Name: {name}
Trigger Type: {trigger_type}
Trigger Config: {json.dumps(trigger_config or {})}
Steps: {steps}

Call the tool and return the automation_id."""

        return await self.create_task(
            title=f'Create Automation: {name}',
            prompt=prompt,
            agent_type='build',
            priority=3,
        )

    async def task_create_audience(
        self,
        name: str,
        audience_type: str,
        config: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Create a task to build a target audience.
        """
        if audience_type == 'geo':
            tool = 'spotless_create_geo_audience'
            prompt = f"""Use the {tool} MCP tool to create a geographic audience.

Name: {name}
Zip Codes: {config.get('zip_codes', [])}
Platforms: {config.get('platforms', ['facebook', 'tiktok'])}

Call the tool and return the audience_id."""
        elif audience_type == 'lookalike':
            tool = 'spotless_create_lookalike_audience'
            prompt = f"""Use the {tool} MCP tool to create a lookalike audience.

Name: {name}
Source: {config.get('source', 'existing_customers')}
Lookalike Percent: {config.get('lookalike_percent', 1)}
Platforms: {config.get('platforms', ['facebook', 'tiktok'])}

Call the tool and return the audience_id."""
        else:
            tool = 'spotless_create_custom_audience'
            prompt = f"""Use the {tool} MCP tool to create a custom audience.

Name: {name}
Emails: {len(config.get('emails', []))} contacts
Phones: {len(config.get('phones', []))} contacts
Platforms: {config.get('platforms', ['facebook', 'tiktok', 'google'])}

Call the tool and return the audience_id."""

        return await self.create_task(
            title=f'Create Audience: {name}',
            prompt=prompt,
            agent_type='build',
            priority=4,
        )

    async def task_get_metrics(
        self,
        start_date: str,
        end_date: str,
        initiative_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Create a task to get unified marketing metrics.
        """
        prompt = f"""Use the spotless_get_unified_metrics MCP tool to get marketing metrics.

Start Date: {start_date}
End Date: {end_date}
Initiative ID: {initiative_id or 'all'}

Call the tool and return the metrics including:
- Total impressions, clicks, conversions
- Spend and ROAS
- CTR and CPC
- Platform breakdown"""

        return await self.create_task(
            title=f'Get Metrics: {start_date} to {end_date}',
            prompt=prompt,
            agent_type='explore',
            priority=2,
        )

    async def task_optimize_budget(
        self,
        channels: Optional[List[str]] = None,
        initiative_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Create a task to get Thompson Sampling budget recommendations.
        """
        channels = channels or ['meta_ads', 'tiktok_ads', 'door_hangers']

        prompt = f"""Use the spotless_thompson_sample_budget MCP tool to get optimal budget allocation.

Channels: {channels}
Initiative ID: {initiative_id or 'all'}

Call the tool and return:
- Recommended allocation per channel (percentages)
- Decision type (explore vs exploit)
- Any recommendations for budget changes"""

        return await self.create_task(
            title='Optimize Budget Allocation',
            prompt=prompt,
            agent_type='explore',
            priority=3,
        )

    # =========================================================================
    # INITIATIVE ORCHESTRATION
    # =========================================================================

    async def execute_initiative(
        self, initiative: Initiative
    ) -> Dict[str, Any]:
        """
        Execute a marketing initiative by creating and coordinating tasks.

        This is the main orchestration method that:
        1. Plans the strategy using AI
        2. Creates tasks for each phase
        3. Monitors completion
        4. Adapts as needed
        """
        logger.info(f'Executing initiative: {initiative.name}')

        results = {
            'initiative_id': str(initiative.id),
            'phases_completed': [],
            'tasks_created': [],
            'errors': [],
        }

        try:
            # Phase 1: Plan the strategy
            if not initiative.strategy:
                logger.info('Planning strategy...')
                strategy = await self._plan_strategy(initiative)
                if strategy:
                    initiative.strategy = strategy
                    initiative.status = InitiativeStatus.EXECUTING
                    await self.initiative_manager.update_initiative(initiative)
                else:
                    results['errors'].append('Failed to plan strategy')
                    return results

            strategy = initiative.strategy

            # Phase 2: Create audiences (parallel tasks)
            if strategy.get('audiences'):
                logger.info('Creating audience tasks...')
                audience_tasks = []
                for audience_config in strategy['audiences'].get('targets', []):
                    task = await self.task_create_audience(
                        name=audience_config.get('name', 'Target Audience'),
                        audience_type=audience_config.get('type', 'geo'),
                        config=audience_config,
                    )
                    if task:
                        audience_tasks.append(task)
                        results['tasks_created'].append(task['id'])

                # Wait for audience tasks
                for task in audience_tasks:
                    await self.wait_for_task(task['id'])

                results['phases_completed'].append('audiences')

            # Phase 3: Generate creatives (parallel tasks)
            if strategy.get('creatives'):
                logger.info('Creating creative generation tasks...')
                creative_tasks = []
                for concept in strategy['creatives'].get('concepts', []):
                    task = await self.task_generate_creative(
                        concept=concept,
                        aspect_ratio=strategy['creatives'].get(
                            'aspect_ratio', '1:1'
                        ),
                        initiative_id=str(initiative.id),
                    )
                    if task:
                        creative_tasks.append(task)
                        results['tasks_created'].append(task['id'])

                # Wait for creative tasks
                for task in creative_tasks:
                    await self.wait_for_task(task['id'])

                results['phases_completed'].append('creatives')

            # Phase 4: Launch campaigns
            if strategy.get('campaigns'):
                logger.info('Creating campaign launch tasks...')
                campaign_config = strategy['campaigns']

                task = await self.task_create_campaign(
                    name=f'{initiative.name} Campaign',
                    platforms=campaign_config.get('platforms', ['facebook']),
                    budget=campaign_config.get('budget_per_platform', 100),
                    initiative_id=str(initiative.id),
                )
                if task:
                    results['tasks_created'].append(task['id'])
                    await self.wait_for_task(task['id'])

                results['phases_completed'].append('campaigns')

            # Phase 5: Set up automations
            if strategy.get('automations'):
                logger.info('Creating automation tasks...')
                for workflow in strategy['automations'].get('workflows', []):
                    task = await self.task_create_automation(
                        name=f'{initiative.name} - {workflow.get("trigger", "workflow")}',
                        trigger_type=workflow.get('trigger', 'form_submit'),
                        steps=workflow.get('sequence', []),
                    )
                    if task:
                        results['tasks_created'].append(task['id'])

                results['phases_completed'].append('automations')

            # Update initiative status
            initiative.status = InitiativeStatus.MONITORING
            initiative.completed_phases = results['phases_completed']
            await self.initiative_manager.update_initiative(initiative)

            logger.info(f'Initiative {initiative.name} execution complete')

        except Exception as e:
            logger.error(f'Error executing initiative: {e}')
            results['errors'].append(str(e))

        return results

    async def _plan_strategy(self, initiative: Initiative) -> Optional[Dict]:
        """Use AI to plan the initiative strategy."""
        if not self.config.azure_endpoint or not self.config.azure_api_key:
            # Return a default strategy if no AI configured
            return self._default_strategy(initiative)

        try:
            session = await self._get_session()

            system_prompt = self._get_system_prompt()
            user_prompt = self._build_strategy_prompt(initiative)

            async with session.post(
                f'{self.config.azure_endpoint}/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {self.config.azure_api_key}',
                    'Content-Type': 'application/json',
                },
                json={
                    'model': self.config.model,
                    'messages': [
                        {'role': 'system', 'content': system_prompt},
                        {'role': 'user', 'content': user_prompt},
                    ],
                    'temperature': 0.7,
                    'max_tokens': 4000,
                },
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    content = data['choices'][0]['message']['content']
                    return self._parse_strategy_response(content)
                else:
                    logger.error(f'AI planning failed: {resp.status}')
                    return self._default_strategy(initiative)

        except Exception as e:
            logger.error(f'Error in AI planning: {e}')
            return self._default_strategy(initiative)

    def _default_strategy(self, initiative: Initiative) -> Dict:
        """Return a default strategy when AI is not available."""
        return {
            'summary': f'Default strategy for {initiative.name}',
            'audiences': {
                'targets': [
                    {
                        'type': 'geo',
                        'zip_codes': ['78701', '78702'],
                        'name': 'Austin Central',
                    }
                ]
            },
            'creatives': {
                'concepts': [
                    'Clean bins, fresh start',
                    'Say goodbye to bin odors',
                ],
                'aspect_ratio': '1:1',
            },
            'campaigns': {
                'platforms': ['facebook'],
                'budget_per_platform': initiative.budget / 2
                if initiative.budget
                else 100,
            },
            'automations': {
                'workflows': [
                    {
                        'trigger': 'form_submit',
                        'sequence': [
                            'welcome_email',
                            'wait_2_days',
                            'follow_up_sms',
                        ],
                    }
                ]
            },
        }

    def _get_system_prompt(self) -> str:
        """Get the system prompt for the Marketing Coordinator."""
        return """You are the Marketing Coordinator for Spotless Bin Co, a trash bin cleaning company.

Create strategic marketing plans that include:
1. Target audiences (geographic, lookalike, custom)
2. Channels (Facebook, TikTok, Google Ads)
3. Ad creative concepts
4. Automation workflows

Output JSON format:
{
  "summary": "Brief description",
  "audiences": {
    "targets": [
      {"type": "geo", "zip_codes": ["78701"], "name": "Austin Central"},
      {"type": "lookalike", "source": "existing_customers", "name": "Customer Lookalike"}
    ]
  },
  "creatives": {
    "concepts": ["Concept 1", "Concept 2"],
    "aspect_ratio": "1:1"
  },
  "campaigns": {
    "platforms": ["facebook", "tiktok"],
    "budget_per_platform": 500
  },
  "automations": {
    "workflows": [
      {"trigger": "form_submit", "sequence": ["welcome_email", "wait_2_days", "follow_up_sms"]}
    ]
  }
}"""

    def _build_strategy_prompt(self, initiative: Initiative) -> str:
        """Build a prompt for strategy planning."""
        return f"""Create a marketing strategy for:

Name: {initiative.name}
Goal: {initiative.goal}
Budget: ${initiative.budget or 'Not specified'}
Context: {json.dumps(initiative.context or {})}

Output JSON only."""

    def _parse_strategy_response(self, content: str) -> Optional[Dict]:
        """Parse the AI response into a strategy dict."""
        import re

        try:
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                return json.loads(json_match.group())
            return None
        except json.JSONDecodeError:
            logger.error(f'Failed to parse strategy JSON')
            return None

    # =========================================================================
    # AGENT LIFECYCLE
    # =========================================================================

    async def register_with_a2a(self) -> bool:
        """Register this agent with the A2A server."""
        try:
            session = await self._get_session()

            async with session.post(
                f'{self.config.a2a_server_url}/v1/monitor/agents/register',
                json={
                    'name': self.config.agent_name,
                    'description': self.AGENT_CARD['description'],
                    'url': f'{self.config.a2a_server_url}/agents/{self.config.agent_id}',
                    'capabilities': self.AGENT_CARD['capabilities'],
                },
            ) as resp:
                if resp.status in (200, 201):
                    logger.info('Registered with A2A server')
                    return True
                else:
                    logger.error(f'Failed to register: {resp.status}')
                    return False

        except Exception as e:
            logger.error(f'Error registering: {e}')
            return False

    async def start(self):
        """Start the Marketing Coordinator agent."""
        logger.info('Starting Marketing Coordinator Agent...')
        self.running = True

        await self.register_with_a2a()
        await self.initiative_manager.initialize()

        # Main loop - check for initiatives to execute
        while self.running:
            try:
                active = await self.initiative_manager.get_active_initiatives()

                for initiative in active:
                    if initiative.status == InitiativeStatus.PLANNING:
                        await self.execute_initiative(initiative)

                await asyncio.sleep(self.config.poll_interval)

            except Exception as e:
                logger.error(f'Error in main loop: {e}')
                await asyncio.sleep(5)

    async def stop(self):
        """Stop the agent gracefully."""
        logger.info('Stopping Marketing Coordinator Agent...')
        self.running = False

        if self.session and not self.session.closed:
            await self.session.close()


async def main():
    """Main entry point for the Marketing Coordinator Agent."""
    import argparse

    parser = argparse.ArgumentParser(description='Marketing Coordinator Agent')
    parser.add_argument(
        '--a2a-server',
        default=os.environ.get('A2A_SERVER_URL', 'http://localhost:8000'),
    )
    parser.add_argument('--log-level', default='INFO')

    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    )

    config = MarketingCoordinatorConfig(a2a_server_url=args.a2a_server)
    agent = MarketingCoordinatorAgent(config)

    try:
        await agent.start()
    except KeyboardInterrupt:
        await agent.stop()


if __name__ == '__main__':
    asyncio.run(main())
