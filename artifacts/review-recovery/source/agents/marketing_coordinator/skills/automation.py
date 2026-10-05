"""
Automation Skill - Creates and manages automation workflows.
"""

import logging
from typing import Any, Dict, List, Optional

from .base import BaseSkill

logger = logging.getLogger(__name__)


class AutomationSkill(BaseSkill):
    """
    Skill for creating and managing automation workflows.

    Delegates to the Automations service in spotlessbinco which handles
    email sequences, SMS campaigns, and multi-touch nurturing flows.
    """

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute automation management task."""
        action = task.get('action', 'create')

        if action == 'create':
            return await self.create_workflow(
                initiative_id=task.get('initiative_id'),
                workflow=task.get('workflow', {}),
            )
        elif action == 'activate':
            return await self.activate_automation(task.get('automation_id'))
        elif action == 'pause':
            return await self.pause_automation(task.get('automation_id'))
        elif action == 'trigger':
            return await self.trigger_automation(
                trigger_type=task.get('trigger_type'),
                context=task.get('context', {}),
            )
        else:
            return {'error': f'Unknown action: {action}'}

    async def create_workflow(
        self,
        initiative_id: Optional[str],
        workflow: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Create an automation workflow.

        Args:
            initiative_id: Optional ID of the parent initiative
            workflow: Workflow configuration including:
                - name: Workflow name
                - trigger: Trigger type (form_submit, tag_added, etc.)
                - trigger_config: Trigger-specific configuration
                - steps: List of workflow steps

        Returns:
            Dict with automation_id, status
        """
        logger.info(
            f'Creating automation workflow: {workflow.get("name", "Unnamed")}'
        )

        # Build nodes and edges from the workflow definition
        nodes, edges = self._build_workflow_graph(workflow)

        result = await self._call_orpc(
            'automations/create',
            {
                'name': workflow.get(
                    'name', f'Initiative {initiative_id} Automation'
                ),
                'nodes': nodes,
                'edges': edges,
            },
        )

        if result.get('success'):
            # Activate if specified
            if workflow.get('auto_activate', True):
                await self.activate_automation(result.get('id'))

        return result

    def _build_workflow_graph(
        self, workflow: Dict[str, Any]
    ) -> tuple[List[Dict], List[Dict]]:
        """Build nodes and edges from workflow definition."""
        nodes = []
        edges = []

        trigger = workflow.get('trigger', 'form_submit')
        trigger_config = workflow.get('trigger_config', {})
        steps = workflow.get('steps', workflow.get('sequence', []))

        # Start node
        start_node_id = 'start-1'
        nodes.append(
            {
                'id': start_node_id,
                'type': 'trigger',
                'position': {'x': 100, 'y': 100},
                'data': {
                    'type': 'start',
                    'label': 'Start',
                    'config': {
                        'trigger': trigger,
                        **trigger_config,
                    },
                },
            }
        )

        prev_node_id = start_node_id
        y_pos = 200

        for i, step in enumerate(steps):
            node_id = f'node-{i + 1}'
            node_type = self._parse_step_type(step)
            node_config = self._parse_step_config(step)

            nodes.append(
                {
                    'id': node_id,
                    'type': 'action',
                    'position': {'x': 100, 'y': y_pos},
                    'data': {
                        'type': node_type,
                        'label': step
                        if isinstance(step, str)
                        else step.get('name', node_type),
                        'config': node_config,
                    },
                }
            )

            edges.append(
                {
                    'id': f'edge-{prev_node_id}-{node_id}',
                    'source': prev_node_id,
                    'target': node_id,
                }
            )

            prev_node_id = node_id
            y_pos += 100

        # End node
        end_node_id = 'end-1'
        nodes.append(
            {
                'id': end_node_id,
                'type': 'end',
                'position': {'x': 100, 'y': y_pos},
                'data': {
                    'type': 'end',
                    'label': 'End',
                    'config': {},
                },
            }
        )

        edges.append(
            {
                'id': f'edge-{prev_node_id}-{end_node_id}',
                'source': prev_node_id,
                'target': end_node_id,
            }
        )

        return nodes, edges

    def _parse_step_type(self, step: Any) -> str:
        """Parse the step type from a step definition."""
        if isinstance(step, str):
            # Parse string format like "welcome_email", "wait_2_days", "follow_up_sms"
            if step.startswith('wait'):
                return 'wait'
            elif 'email' in step:
                return 'email'
            elif 'sms' in step:
                return 'sms'
            elif 'call' in step:
                return 'call'
            elif 'mail' in step:
                return 'direct_mail'
            elif 'tag' in step:
                return 'tag'
            else:
                return 'action'
        elif isinstance(step, dict):
            return step.get('type', 'action')
        return 'action'

    def _parse_step_config(self, step: Any) -> Dict[str, Any]:
        """Parse the step configuration from a step definition."""
        if isinstance(step, str):
            # Parse string format
            if step.startswith('wait_'):
                # Parse "wait_2_days" format
                parts = step.split('_')
                if len(parts) >= 3:
                    duration = int(parts[1]) if parts[1].isdigit() else 1
                    unit = parts[2]
                    return {'duration': duration, 'unit': unit}
                return {'duration': 1, 'unit': 'days'}
            elif 'email' in step:
                return {'templateName': step}
            elif 'sms' in step:
                return {'templateName': step}
            else:
                return {}
        elif isinstance(step, dict):
            return step.get('config', step)
        return {}

    async def activate_automation(self, automation_id: str) -> Dict[str, Any]:
        """Activate an automation workflow."""
        logger.info(f'Activating automation: {automation_id}')

        return await self._call_orpc(
            'automations/updateStatus',
            {
                'id': automation_id,
                'status': 'active',
            },
        )

    async def pause_automation(self, automation_id: str) -> Dict[str, Any]:
        """Pause an automation workflow."""
        logger.info(f'Pausing automation: {automation_id}')

        return await self._call_orpc(
            'automations/updateStatus',
            {
                'id': automation_id,
                'status': 'paused',
            },
        )

    async def trigger_automation(
        self,
        trigger_type: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Manually trigger automations of a specific type.

        Args:
            trigger_type: Type of trigger (decline_upsell, tag_added, etc.)
            context: Trigger context including leadId, customerId, email, etc.

        Returns:
            Dict with triggered count and any errors
        """
        logger.info(f'Triggering automations of type: {trigger_type}')

        return await self._call_orpc(
            'automations/trigger',
            {
                'triggerType': trigger_type,
                **context,
            },
        )

    async def list_automations(
        self,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List all automations, optionally filtered by status."""
        return await self._call_orpc(
            'automations/list',
            {'status': status} if status else {},
        )

    async def get_automation(self, automation_id: str) -> Dict[str, Any]:
        """Get details of a specific automation."""
        return await self._call_orpc(
            'automations/get',
            {'id': automation_id},
        )
