"""
Message broker for real-time inter-agent communication.

Provides pub/sub messaging capabilities using Redis for agent discovery,
event streaming, and push notifications.
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Callable, Any, Set
from datetime import datetime

import redis.asyncio as redis_async
from redis.asyncio import Redis

from .models import AgentCard, Message, TaskStatusUpdateEvent


logger = logging.getLogger(__name__)


class MessageBroker:
    """Redis-based message broker for A2A agent communication."""

    def __init__(self, redis_url: str = 'redis://localhost:6379'):
        self.redis_url = redis_url
        self.redis: Optional[Redis] = None
        self.pub_redis: Optional[Redis] = None
        self._subscribers: Dict[str, Set[Callable[[str, Any], None]]] = {}
        self._subscription_tasks: Dict[str, asyncio.Task] = {}
        self._running = False

    async def start(self) -> None:
        """Start the message broker and connect to Redis."""
        try:
            # Create separate connections for pub/sub operations
            self.redis = redis_async.from_url(self.redis_url)
            self.pub_redis = redis_async.from_url(self.redis_url)
            self._running = True
            logger.info(
                f'Message broker connected to Redis at {self.redis_url}'
            )
        except Exception as e:
            logger.error(f'Failed to connect to Redis: {e}')
            raise

    async def stop(self) -> None:
        """Stop the message broker and close connections."""
        self._running = False

        # Cancel all subscription tasks
        for task in self._subscription_tasks.values():
            task.cancel()

        # Wait for tasks to complete
        if self._subscription_tasks:
            await asyncio.gather(
                *self._subscription_tasks.values(), return_exceptions=True
            )

        # Close Redis connections
        if self.redis:
            await self.redis.close()
        if self.pub_redis:
            await self.pub_redis.close()

        logger.info('Message broker stopped')

    async def register_agent(
        self,
        agent_card: AgentCard,
        role: Optional[str] = None,
        instance_id: Optional[str] = None,
        models_supported: Optional[List[str]] = None,
    ) -> None:
        """
        Register an agent in the discovery registry.

        Args:
            agent_card: The agent's card with name, description, url, capabilities
            role: Optional routing role (e.g., "code-reviewer"). If the agent name
                  follows the pattern "role:instance", role is extracted automatically.
            instance_id: Optional unique instance identifier for this agent.
            models_supported: List of model identifiers this agent supports
                              (normalized format: "provider:model", e.g., "openai:gpt-4.1").
        """
        if not self.redis:
            raise RuntimeError('Message broker not started')

        # Extract role from name if not provided (pattern: "role:instance")
        # This allows send_to_agent(role="code-reviewer") to route correctly
        extracted_role = role
        extracted_instance = instance_id
        if ':' in agent_card.name and not role:
            parts = agent_card.name.split(':', 1)
            extracted_role = parts[0]
            extracted_instance = parts[1] if len(parts) > 1 else instance_id

        # Store agent card in registry
        agent_key = f'agents:{agent_card.name}'
        agent_data = agent_card.model_dump_json()

        mapping = {
            'card': agent_data,
            'last_seen': datetime.utcnow().isoformat(),
            'status': 'active',
        }
        # Store role and instance_id for discovery enrichment
        if extracted_role:
            mapping['role'] = extracted_role
        if extracted_instance:
            mapping['instance_id'] = extracted_instance
        # Store models_supported for model-aware routing
        if models_supported:
            mapping['models_supported'] = json.dumps(models_supported)

        await self.redis.hset(agent_key, mapping=mapping)

        # Add to agents set for discovery
        await self.redis.sadd('agents:registry', agent_card.name)

        # Also index by role for faster role-based lookups
        if extracted_role:
            await self.redis.sadd(
                f'agents:role:{extracted_role}', agent_card.name
            )

        # Publish agent registration event
        await self.publish_event(
            'agent.registered',
            {
                'agent_name': agent_card.name,
                'timestamp': datetime.utcnow().isoformat(),
            },
        )

        logger.info(f'Registered agent: {agent_card.name}')

    async def unregister_agent(self, agent_name: str) -> None:
        """Unregister an agent from the discovery registry."""
        if not self.redis:
            raise RuntimeError('Message broker not started')

        agent_key = f'agents:{agent_name}'

        # Mark as inactive
        await self.redis.hset(agent_key, 'status', 'inactive')

        # Remove from active agents set
        await self.redis.srem('agents:registry', agent_name)

        # Publish agent unregistration event
        await self.publish_event(
            'agent.unregistered',
            {
                'agent_name': agent_name,
                'timestamp': datetime.utcnow().isoformat(),
            },
        )

        logger.info(f'Unregistered agent: {agent_name}')

    async def discover_agents(
        self,
        max_age_seconds: int = 120,
        cleanup_stale: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Discover all registered agents that are still alive.

        Args:
            max_age_seconds: Filter out agents not seen within this many seconds.
                             Default 120s (2 minutes). Set to 0 to disable filtering.
            cleanup_stale: If True, remove stale agents from registry (lazy cleanup).

        Returns:
            List of dicts with agent info including:
            - name: Full unique name (e.g., "code-reviewer:dev-vm:abc123")
            - role: Routing role for send_to_agent (e.g., "code-reviewer")
            - instance_id: Unique instance identifier (e.g., "dev-vm:abc123")
            - description, url, capabilities: From AgentCard
            - last_seen: ISO timestamp of last heartbeat

        Note: send_to_agent expects the 'role' field for routing, not 'name'.
        The 'name' field is the unique discovery identity for debugging.
        """
        if not self.redis:
            raise RuntimeError('Message broker not started')

        agent_names = await self.redis.smembers('agents:registry')
        agents = []
        now = datetime.utcnow()
        stale_agents = []

        for agent_name in agent_names:
            name_str = (
                agent_name.decode()
                if isinstance(agent_name, bytes)
                else agent_name
            )
            agent_key = f'agents:{name_str}'
            agent_hash = await self.redis.hgetall(agent_key)

            if not agent_hash:
                stale_agents.append(
                    name_str
                )  # Key exists in set but hash is gone
                continue

            # Check TTL - filter out stale agents
            last_seen_str = agent_hash.get(b'last_seen')
            last_seen_iso = None
            if last_seen_str:
                try:
                    last_seen_decoded = (
                        last_seen_str.decode()
                        if isinstance(last_seen_str, bytes)
                        else last_seen_str
                    )
                    last_seen = datetime.fromisoformat(last_seen_decoded)
                    last_seen_iso = last_seen_decoded
                    age_seconds = (now - last_seen).total_seconds()
                    # Clock skew tolerance: treat future timestamps as "just seen"
                    # This handles worker clocks slightly ahead of server clock
                    if age_seconds < 0:
                        age_seconds = 0
                    if max_age_seconds > 0 and age_seconds > max_age_seconds:
                        stale_agents.append(name_str)
                        logger.debug(
                            f"Filtering stale agent '{name_str}' "
                            f'(last seen {age_seconds:.0f}s ago, max={max_age_seconds}s)'
                        )
                        continue
                except (ValueError, TypeError) as e:
                    logger.debug(
                        f'Could not parse last_seen for {name_str}: {e}'
                    )
                    # If we can't parse last_seen, include it (benefit of doubt)

            # Extract role and instance_id
            role = agent_hash.get(b'role')
            instance_id = agent_hash.get(b'instance_id')
            role_str = role.decode() if isinstance(role, bytes) else role
            instance_str = (
                instance_id.decode()
                if isinstance(instance_id, bytes)
                else instance_id
            )

            # Extract models_supported
            models_raw = agent_hash.get(b'models_supported')
            models_supported = None
            if models_raw:
                try:
                    models_decoded = (
                        models_raw.decode()
                        if isinstance(models_raw, bytes)
                        else models_raw
                    )
                    models_supported = json.loads(models_decoded)
                except (json.JSONDecodeError, TypeError):
                    pass

            # Parse agent card
            agent_data = agent_hash.get(b'card')
            if agent_data:
                try:
                    agent_card = AgentCard.model_validate_json(agent_data)
                    # Build enriched discovery response
                    agent_info = {
                        'name': name_str,  # Unique discovery identity
                        'role': role_str or name_str.split(':')[0]
                        if ':' in name_str
                        else name_str,
                        'instance_id': instance_str,
                        'description': agent_card.description,
                        'url': agent_card.url,
                        'capabilities': agent_card.capabilities.model_dump()
                        if agent_card.capabilities
                        else {},
                        'models_supported': models_supported,
                        'last_seen': last_seen_iso,
                    }
                    agents.append(agent_info)
                except Exception as e:
                    logger.warning(
                        f'Failed to parse agent card for {name_str}: {e}'
                    )

        # Lazy cleanup: remove stale agents from ALL indexes to prevent accumulation
        if stale_agents and cleanup_stale:
            logger.info(
                f'Cleaning up {len(stale_agents)} stale agents from registry: {stale_agents}'
            )
            for stale_name in stale_agents:
                try:
                    # 1. Remove from main registry set
                    await self.redis.srem('agents:registry', stale_name)

                    # 2. Get role from stored hash (more reliable than parsing name)
                    agent_key = f'agents:{stale_name}'
                    stored_role = await self.redis.hget(agent_key, 'role')
                    if stored_role:
                        role_str = (
                            stored_role.decode()
                            if isinstance(stored_role, bytes)
                            else stored_role
                        )
                        await self.redis.srem(
                            f'agents:role:{role_str}', stale_name
                        )
                    elif ':' in stale_name:
                        # Fallback: infer role from name pattern
                        role = stale_name.split(':')[0]
                        await self.redis.srem(f'agents:role:{role}', stale_name)

                    # 3. Mark hash as stale (keep for forensics, but mark inactive)
                    await self.redis.hset(
                        agent_key,
                        mapping={
                            'status': 'stale',
                            'stale_at': datetime.utcnow().isoformat(),
                        },
                    )

                    logger.debug(f'Cleaned up stale agent: {stale_name}')
                except Exception as e:
                    logger.debug(
                        f'Failed to cleanup stale agent {stale_name}: {e}'
                    )

        return agents

    async def discover_agents_by_role(self, role: str) -> List[Dict[str, Any]]:
        """
        Discover agents by their routing role.

        Args:
            role: The routing role (e.g., "code-reviewer")

        Returns:
            List of active agents with that role.
        """
        if not self.redis:
            raise RuntimeError('Message broker not started')

        # Get agents indexed by role
        role_members = await self.redis.smembers(f'agents:role:{role}')
        if not role_members:
            return []

        # Filter to only active ones
        all_agents = await self.discover_agents()
        return [a for a in all_agents if a.get('role') == role]

    async def refresh_agent_heartbeat(self, agent_name: str) -> bool:
        """
        Refresh the last_seen timestamp for an agent.

        Call this periodically (e.g., every 30s) to keep the agent
        visible in discovery. Agents not refreshed within max_age_seconds
        will be filtered out of discover_agents results.

        Args:
            agent_name: The agent's registered name

        Returns:
            True if the agent exists and was refreshed, False otherwise.
        """
        if not self.redis:
            raise RuntimeError('Message broker not started')

        agent_key = f'agents:{agent_name}'

        # Check if agent exists
        exists = await self.redis.exists(agent_key)
        if not exists:
            logger.debug(
                f'Cannot refresh heartbeat for unknown agent: {agent_name}'
            )
            return False

        # Update last_seen
        await self.redis.hset(
            agent_key, 'last_seen', datetime.utcnow().isoformat()
        )
        logger.debug(f'Refreshed heartbeat for agent: {agent_name}')
        return True

    async def get_agent(self, agent_name: str) -> Optional[AgentCard]:
        """Get a specific agent's card."""
        if not self.redis:
            raise RuntimeError('Message broker not started')

        agent_key = f'agents:{agent_name}'
        agent_data = await self.redis.hget(agent_key, 'card')

        if agent_data:
            try:
                return AgentCard.model_validate_json(agent_data)
            except Exception as e:
                logger.warning(
                    f'Failed to parse agent card for {agent_name}: {e}'
                )

        return None

    async def publish_event(self, event_type: str, data: Any) -> None:
        """Publish an event to all subscribers."""
        if not self.pub_redis:
            raise RuntimeError('Message broker not started')

        event_data = {
            'type': event_type,
            'data': data,
            'timestamp': datetime.utcnow().isoformat(),
        }

        # Publish to global events channel
        await self.pub_redis.publish('events', json.dumps(event_data))

        # Publish to event-specific channel
        await self.pub_redis.publish(
            f'events:{event_type}', json.dumps(event_data)
        )

    async def publish(self, event_type: str, data: Any) -> None:
        """Alias for publish_event for compatibility."""
        await self.publish_event(event_type, data)

    async def publish_task_update(
        self, agent_name: str, event: TaskStatusUpdateEvent
    ) -> None:
        """Publish a task status update event."""
        await self.publish_event(
            'task.updated',
            {
                'agent_name': agent_name,
                'task_id': event.task.id,
                'status': event.task.status.value,
                'final': event.final,
                'timestamp': event.task.updated_at.isoformat(),
            },
        )

    async def publish_message(
        self, from_agent: str, to_agent: str, message: Message
    ) -> None:
        """Publish a message between agents."""
        await self.publish_event(
            'message.sent',
            {
                'from_agent': from_agent,
                'to_agent': to_agent,
                'message': message.model_dump(),
                'timestamp': datetime.utcnow().isoformat(),
            },
        )

    async def subscribe_to_events(
        self, event_type: str, handler: Callable[[str, Any], None]
    ) -> None:
        """Subscribe to events of a specific type."""
        if not self._running:
            raise RuntimeError('Message broker not started')

        channel = f'events:{event_type}'

        if channel not in self._subscribers:
            self._subscribers[channel] = set()
            # Start subscription task for this channel
            task = asyncio.create_task(self._subscription_loop(channel))
            self._subscription_tasks[channel] = task

        self._subscribers[channel].add(handler)
        logger.info(f'Subscribed to events: {event_type}')

    async def unsubscribe_from_events(
        self, event_type: str, handler: Callable[[str, Any], None]
    ) -> None:
        """Unsubscribe from events of a specific type."""
        channel = f'events:{event_type}'

        if channel in self._subscribers:
            self._subscribers[channel].discard(handler)

            # If no more subscribers, cancel the subscription task
            if not self._subscribers[channel]:
                del self._subscribers[channel]
                if channel in self._subscription_tasks:
                    self._subscription_tasks[channel].cancel()
                    del self._subscription_tasks[channel]

        logger.info(f'Unsubscribed from events: {event_type}')

    async def _subscription_loop(self, channel: str) -> None:
        """Handle subscriptions for a specific channel."""
        if not self.redis:
            return

        try:
            pubsub = self.redis.pubsub()
            await pubsub.subscribe(channel)

            async for message in pubsub.listen():
                if not self._running:
                    break

                if message['type'] == 'message':
                    try:
                        event_data = json.loads(message['data'])
                        event_type = event_data.get('type', '')
                        data = event_data.get('data', {})

                        # Notify all handlers for this channel
                        handlers = self._subscribers.get(channel, set()).copy()
                        for handler in handlers:
                            try:
                                if asyncio.iscoroutinefunction(handler):
                                    await handler(event_type, data)
                                else:
                                    handler(event_type, data)
                            except Exception as e:
                                logger.error(f'Error in event handler: {e}')

                    except json.JSONDecodeError as e:
                        logger.warning(f'Failed to decode event data: {e}')

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f'Error in subscription loop for {channel}: {e}')
        finally:
            try:
                await pubsub.close()
            except:
                pass


class InMemoryMessageBroker:
    """In-memory message broker for testing and development."""

    def __init__(self):
        self._agents: Dict[str, AgentCard] = {}
        self._agent_last_seen: Dict[
            str, datetime
        ] = {}  # Track last_seen for TTL filtering
        self._agent_roles: Dict[str, str] = {}  # name -> role mapping
        self._agent_instance_ids: Dict[
            str, str
        ] = {}  # name -> instance_id mapping
        self._agent_models: Dict[
            str, List[str]
        ] = {}  # name -> models_supported mapping
        self._subscribers: Dict[str, List[Callable[[str, Any], None]]] = {}
        self._running = False

    async def start(self) -> None:
        """Start the in-memory broker."""
        self._running = True
        logger.info('In-memory message broker started')

    async def stop(self) -> None:
        """Stop the in-memory broker."""
        self._running = False
        self._subscribers.clear()
        logger.info('In-memory message broker stopped')

    async def register_agent(
        self,
        agent_card: AgentCard,
        role: Optional[str] = None,
        instance_id: Optional[str] = None,
        models_supported: Optional[List[str]] = None,
    ) -> None:
        """Register an agent."""
        self._agents[agent_card.name] = agent_card
        self._agent_last_seen[agent_card.name] = datetime.utcnow()

        # Extract role from name if not provided
        if role:
            self._agent_roles[agent_card.name] = role
        elif ':' in agent_card.name:
            self._agent_roles[agent_card.name] = agent_card.name.split(':')[0]

        if instance_id:
            self._agent_instance_ids[agent_card.name] = instance_id
        elif ':' in agent_card.name:
            parts = agent_card.name.split(':', 1)
            if len(parts) > 1:
                self._agent_instance_ids[agent_card.name] = parts[1]

        # Store models_supported
        if models_supported:
            self._agent_models[agent_card.name] = models_supported

        await self.publish_event(
            'agent.registered',
            {
                'agent_name': agent_card.name,
                'timestamp': datetime.utcnow().isoformat(),
            },
        )

    async def unregister_agent(self, agent_name: str) -> None:
        """Unregister an agent."""
        self._agents.pop(agent_name, None)
        self._agent_last_seen.pop(agent_name, None)
        self._agent_roles.pop(agent_name, None)
        self._agent_instance_ids.pop(agent_name, None)
        self._agent_models.pop(agent_name, None)
        await self.publish_event(
            'agent.unregistered',
            {
                'agent_name': agent_name,
                'timestamp': datetime.utcnow().isoformat(),
            },
        )

    async def discover_agents(
        self,
        max_age_seconds: int = 120,
        cleanup_stale: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Discover all registered agents that are still alive.

        Returns enriched agent info with role and instance_id.
        """
        now = datetime.utcnow()
        active_agents = []
        stale_names = []

        for name, card in list(self._agents.items()):
            last_seen = self._agent_last_seen.get(name)
            last_seen_iso = last_seen.isoformat() if last_seen else None

            if max_age_seconds > 0 and last_seen:
                age = (now - last_seen).total_seconds()
                # Clock skew tolerance: treat future timestamps as "just seen"
                if age < 0:
                    age = 0
                if age > max_age_seconds:
                    stale_names.append(name)
                    continue

            role = self._agent_roles.get(name)
            if not role and ':' in name:
                role = name.split(':')[0]

            agent_info = {
                'name': name,
                'role': role or name,
                'instance_id': self._agent_instance_ids.get(name),
                'description': card.description,
                'url': card.url,
                'capabilities': card.capabilities.model_dump()
                if card.capabilities
                else {},
                'models_supported': self._agent_models.get(name),
                'last_seen': last_seen_iso,
            }
            active_agents.append(agent_info)

        # Lazy cleanup
        if stale_names and cleanup_stale:
            for name in stale_names:
                self._agents.pop(name, None)
                self._agent_last_seen.pop(name, None)
                self._agent_roles.pop(name, None)
                self._agent_instance_ids.pop(name, None)
                self._agent_models.pop(name, None)

        return active_agents

    async def discover_agents_by_role(self, role: str) -> List[Dict[str, Any]]:
        """Discover agents by their routing role."""
        all_agents = await self.discover_agents()
        return [a for a in all_agents if a.get('role') == role]

    async def refresh_agent_heartbeat(self, agent_name: str) -> bool:
        """Refresh the last_seen timestamp for an agent."""
        if agent_name not in self._agents:
            return False
        self._agent_last_seen[agent_name] = datetime.utcnow()
        return True

    async def get_agent(self, agent_name: str) -> Optional[AgentCard]:
        """Get a specific agent's card."""
        return self._agents.get(agent_name)

    async def publish_event(self, event_type: str, data: Any) -> None:
        """Publish an event."""
        if not self._running:
            return

        # Notify subscribers
        for handler in self._subscribers.get(event_type, []):
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event_type, data)
                else:
                    handler(event_type, data)
            except Exception as e:
                logger.error(f'Error in event handler: {e}')

    async def publish(self, event_type: str, data: Any) -> None:
        """Alias for publish_event for compatibility."""
        await self.publish_event(event_type, data)

    async def publish_task_update(
        self, agent_name: str, event: TaskStatusUpdateEvent
    ) -> None:
        """Publish a task status update event."""
        await self.publish_event(
            'task.updated',
            {
                'agent_name': agent_name,
                'task_id': event.task.id,
                'status': event.task.status.value,
                'final': event.final,
                'timestamp': event.task.updated_at.isoformat(),
            },
        )

    async def publish_message(
        self, from_agent: str, to_agent: str, message: Message
    ) -> None:
        """Publish a message between agents."""
        await self.publish_event(
            'message.sent',
            {
                'from_agent': from_agent,
                'to_agent': to_agent,
                'message': message.model_dump(),
                'timestamp': datetime.utcnow().isoformat(),
            },
        )

    async def subscribe_to_events(
        self, event_type: str, handler: Callable[[str, Any], None]
    ) -> None:
        """Subscribe to events."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    async def unsubscribe_from_events(
        self, event_type: str, handler: Callable[[str, Any], None]
    ) -> None:
        """Unsubscribe from events."""
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(handler)
            except ValueError:
                pass
