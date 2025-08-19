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
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
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
            logger.info(f"Message broker connected to Redis at {self.redis_url}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def stop(self) -> None:
        """Stop the message broker and close connections."""
        self._running = False
        
        # Cancel all subscription tasks
        for task in self._subscription_tasks.values():
            task.cancel()
        
        # Wait for tasks to complete
        if self._subscription_tasks:
            await asyncio.gather(*self._subscription_tasks.values(), return_exceptions=True)
        
        # Close Redis connections
        if self.redis:
            await self.redis.close()
        if self.pub_redis:
            await self.pub_redis.close()
        
        logger.info("Message broker stopped")
    
    async def register_agent(self, agent_card: AgentCard) -> None:
        """Register an agent in the discovery registry."""
        if not self.redis:
            raise RuntimeError("Message broker not started")
        
        # Store agent card in registry
        agent_key = f"agents:{agent_card.name}"
        agent_data = agent_card.model_dump_json()
        
        await self.redis.hset(agent_key, mapping={
            "card": agent_data,
            "last_seen": datetime.utcnow().isoformat(),
            "status": "active"
        })
        
        # Add to agents set for discovery
        await self.redis.sadd("agents:registry", agent_card.name)
        
        # Publish agent registration event
        await self.publish_event("agent.registered", {
            "agent_name": agent_card.name,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        logger.info(f"Registered agent: {agent_card.name}")
    
    async def unregister_agent(self, agent_name: str) -> None:
        """Unregister an agent from the discovery registry."""
        if not self.redis:
            raise RuntimeError("Message broker not started")
        
        agent_key = f"agents:{agent_name}"
        
        # Mark as inactive
        await self.redis.hset(agent_key, "status", "inactive")
        
        # Remove from active agents set
        await self.redis.srem("agents:registry", agent_name)
        
        # Publish agent unregistration event
        await self.publish_event("agent.unregistered", {
            "agent_name": agent_name,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        logger.info(f"Unregistered agent: {agent_name}")
    
    async def discover_agents(self) -> List[AgentCard]:
        """Discover all registered agents."""
        if not self.redis:
            raise RuntimeError("Message broker not started")
        
        agent_names = await self.redis.smembers("agents:registry")
        agents = []
        
        for agent_name in agent_names:
            agent_key = f"agents:{agent_name.decode()}"
            agent_data = await self.redis.hget(agent_key, "card")
            
            if agent_data:
                try:
                    agent_card = AgentCard.model_validate_json(agent_data)
                    agents.append(agent_card)
                except Exception as e:
                    logger.warning(f"Failed to parse agent card for {agent_name}: {e}")
        
        return agents
    
    async def get_agent(self, agent_name: str) -> Optional[AgentCard]:
        """Get a specific agent's card."""
        if not self.redis:
            raise RuntimeError("Message broker not started")
        
        agent_key = f"agents:{agent_name}"
        agent_data = await self.redis.hget(agent_key, "card")
        
        if agent_data:
            try:
                return AgentCard.model_validate_json(agent_data)
            except Exception as e:
                logger.warning(f"Failed to parse agent card for {agent_name}: {e}")
        
        return None
    
    async def publish_event(self, event_type: str, data: Any) -> None:
        """Publish an event to all subscribers."""
        if not self.pub_redis:
            raise RuntimeError("Message broker not started")
        
        event_data = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Publish to global events channel
        await self.pub_redis.publish("events", json.dumps(event_data))
        
        # Publish to event-specific channel
        await self.pub_redis.publish(f"events:{event_type}", json.dumps(event_data))
    
    async def publish_task_update(self, agent_name: str, event: TaskStatusUpdateEvent) -> None:
        """Publish a task status update event."""
        await self.publish_event("task.updated", {
            "agent_name": agent_name,
            "task_id": event.task.id,
            "status": event.task.status.value,
            "final": event.final,
            "timestamp": event.task.updated_at.isoformat()
        })
    
    async def publish_message(self, from_agent: str, to_agent: str, message: Message) -> None:
        """Publish a message between agents."""
        await self.publish_event("message.sent", {
            "from_agent": from_agent,
            "to_agent": to_agent,
            "message": message.model_dump(),
            "timestamp": datetime.utcnow().isoformat()
        })
    
    async def subscribe_to_events(
        self,
        event_type: str,
        handler: Callable[[str, Any], None]
    ) -> None:
        """Subscribe to events of a specific type."""
        if not self._running:
            raise RuntimeError("Message broker not started")
        
        channel = f"events:{event_type}"
        
        if channel not in self._subscribers:
            self._subscribers[channel] = set()
            # Start subscription task for this channel
            task = asyncio.create_task(self._subscription_loop(channel))
            self._subscription_tasks[channel] = task
        
        self._subscribers[channel].add(handler)
        logger.info(f"Subscribed to events: {event_type}")
    
    async def unsubscribe_from_events(
        self,
        event_type: str,
        handler: Callable[[str, Any], None]
    ) -> None:
        """Unsubscribe from events of a specific type."""
        channel = f"events:{event_type}"
        
        if channel in self._subscribers:
            self._subscribers[channel].discard(handler)
            
            # If no more subscribers, cancel the subscription task
            if not self._subscribers[channel]:
                del self._subscribers[channel]
                if channel in self._subscription_tasks:
                    self._subscription_tasks[channel].cancel()
                    del self._subscription_tasks[channel]
        
        logger.info(f"Unsubscribed from events: {event_type}")
    
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
                
                if message["type"] == "message":
                    try:
                        event_data = json.loads(message["data"])
                        event_type = event_data.get("type", "")
                        data = event_data.get("data", {})
                        
                        # Notify all handlers for this channel
                        handlers = self._subscribers.get(channel, set()).copy()
                        for handler in handlers:
                            try:
                                if asyncio.iscoroutinefunction(handler):
                                    await handler(event_type, data)
                                else:
                                    handler(event_type, data)
                            except Exception as e:
                                logger.error(f"Error in event handler: {e}")
                    
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to decode event data: {e}")
        
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in subscription loop for {channel}: {e}")
        finally:
            try:
                await pubsub.close()
            except:
                pass


class InMemoryMessageBroker:
    """In-memory message broker for testing and development."""
    
    def __init__(self):
        self._agents: Dict[str, AgentCard] = {}
        self._subscribers: Dict[str, List[Callable[[str, Any], None]]] = {}
        self._running = False
    
    async def start(self) -> None:
        """Start the in-memory broker."""
        self._running = True
        logger.info("In-memory message broker started")
    
    async def stop(self) -> None:
        """Stop the in-memory broker."""
        self._running = False
        self._subscribers.clear()
        logger.info("In-memory message broker stopped")
    
    async def register_agent(self, agent_card: AgentCard) -> None:
        """Register an agent."""
        self._agents[agent_card.name] = agent_card
        await self.publish_event("agent.registered", {
            "agent_name": agent_card.name,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    async def unregister_agent(self, agent_name: str) -> None:
        """Unregister an agent."""
        self._agents.pop(agent_name, None)
        await self.publish_event("agent.unregistered", {
            "agent_name": agent_name,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    async def discover_agents(self) -> List[AgentCard]:
        """Discover all registered agents."""
        return list(self._agents.values())
    
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
                logger.error(f"Error in event handler: {e}")
    
    async def publish_task_update(self, agent_name: str, event: TaskStatusUpdateEvent) -> None:
        """Publish a task status update event."""
        await self.publish_event("task.updated", {
            "agent_name": agent_name,
            "task_id": event.task.id,
            "status": event.task.status.value,
            "final": event.final,
            "timestamp": event.task.updated_at.isoformat()
        })
    
    async def publish_message(self, from_agent: str, to_agent: str, message: Message) -> None:
        """Publish a message between agents."""
        await self.publish_event("message.sent", {
            "from_agent": from_agent,
            "to_agent": to_agent,
            "message": message.model_dump(),
            "timestamp": datetime.utcnow().isoformat()
        })
    
    async def subscribe_to_events(
        self,
        event_type: str,
        handler: Callable[[str, Any], None]
    ) -> None:
        """Subscribe to events."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
    
    async def unsubscribe_from_events(
        self,
        event_type: str,
        handler: Callable[[str, Any], None]
    ) -> None:
        """Unsubscribe from events."""
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(handler)
            except ValueError:
                pass