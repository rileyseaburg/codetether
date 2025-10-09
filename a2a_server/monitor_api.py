"""
Monitoring API endpoints for A2A Server.

Provides real-time monitoring, logging, and human intervention capabilities.
"""

import asyncio
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from collections import deque
from dataclasses import dataclass, asdict
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse, HTMLResponse, FileResponse
from pydantic import BaseModel
import os

logger = logging.getLogger(__name__)

# Router for monitoring endpoints
monitor_router = APIRouter(prefix="/v1/monitor", tags=["monitoring"])


@dataclass
class MonitorMessage:
    """Represents a monitored message."""
    id: str
    timestamp: datetime
    type: str  # agent, human, system, tool, error
    agent_name: str
    content: str
    metadata: Dict[str, Any]
    response_time: Optional[float] = None
    tokens: Optional[int] = None
    error: Optional[str] = None


class InterventionRequest(BaseModel):
    """Request model for human intervention."""
    agent_id: str
    message: str
    timestamp: str


class MonitoringService:
    """Service for monitoring agent conversations and enabling human intervention."""
    
    def __init__(self):
        self.messages = deque(maxlen=1000)  # Keep last 1000 messages
        self.active_agents = {}
        self.interventions = []
        self.stats = {
            "total_messages": 0,
            "tool_calls": 0,
            "errors": 0,
            "tokens": 0,
            "response_times": deque(maxlen=100)
        }
        self.subscribers = []
        
    async def log_message(
        self,
        agent_name: str,
        content: str,
        message_type: str = "agent",
        metadata: Optional[Dict[str, Any]] = None,
        response_time: Optional[float] = None,
        tokens: Optional[int] = None,
        error: Optional[str] = None
    ):
        """Log a message from an agent or system."""
        message = MonitorMessage(
            id=f"{datetime.now().timestamp()}",
            timestamp=datetime.now(),
            type=message_type,
            agent_name=agent_name,
            content=content,
            metadata=metadata or {},
            response_time=response_time,
            tokens=tokens,
            error=error
        )
        
        self.messages.append(message)
        self.stats["total_messages"] += 1
        
        if message_type == "tool":
            self.stats["tool_calls"] += 1
        if error:
            self.stats["errors"] += 1
        if tokens:
            self.stats["tokens"] += tokens
        if response_time:
            self.stats["response_times"].append(response_time)
        
        # Broadcast to all subscribers
        await self.broadcast_message(message)
        
        logger.info(f"Logged message from {agent_name}: {content[:100]}")
    
    async def broadcast_message(self, message: MonitorMessage):
        """Broadcast a message to all SSE subscribers."""
        data = {
            "type": message.type,
            "agent_name": message.agent_name,
            "content": message.content,
            "metadata": message.metadata,
            "response_time": message.response_time,
            "tokens": message.tokens,
            "error": message.error,
            "timestamp": message.timestamp.isoformat()
        }
        
        message_json = json.dumps(data)
        
        # Remove disconnected subscribers
        self.subscribers = [sub for sub in self.subscribers if not sub.done()]
        
        # Send to all active subscribers
        for queue in self.subscribers:
            try:
                await queue.put(f"data: {message_json}\n\n")
            except:
                pass
    
    def register_agent(self, agent_id: str, agent_name: str):
        """Register an active agent."""
        self.active_agents[agent_id] = {
            "id": agent_id,
            "name": agent_name,
            "status": "active",
            "messages_count": 0,
            "last_seen": datetime.now()
        }
    
    def update_agent_status(self, agent_id: str, status: str):
        """Update agent status."""
        if agent_id in self.active_agents:
            self.active_agents[agent_id]["status"] = status
            self.active_agents[agent_id]["last_seen"] = datetime.now()
    
    async def handle_intervention(self, agent_id: str, message: str):
        """Handle human intervention for an agent."""
        intervention = {
            "agent_id": agent_id,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        
        self.interventions.append(intervention)
        
        # Log the intervention as a message
        agent_name = self.active_agents.get(agent_id, {}).get("name", "Unknown")
        await self.log_message(
            agent_name="Human Operator",
            content=f"Intervention to {agent_name}: {message}",
            message_type="human",
            metadata={"intervention": True, "target_agent": agent_id}
        )
        
        return intervention
    
    def get_messages(self, limit: int = 100, message_type: Optional[str] = None) -> List[Dict]:
        """Get recent messages."""
        messages = list(self.messages)
        
        if message_type:
            messages = [m for m in messages if m.type == message_type]
        
        return [asdict(m) for m in messages[-limit:]]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get monitoring statistics."""
        avg_response_time = 0
        if self.stats["response_times"]:
            avg_response_time = sum(self.stats["response_times"]) / len(self.stats["response_times"])
        
        return {
            "total_messages": self.stats["total_messages"],
            "tool_calls": self.stats["tool_calls"],
            "errors": self.stats["errors"],
            "tokens": self.stats["tokens"],
            "avg_response_time": avg_response_time,
            "active_agents": len(self.active_agents),
            "interventions": len(self.interventions)
        }


# Global monitoring service instance
monitoring_service = MonitoringService()


@monitor_router.get("/")
async def serve_monitor_ui():
    """Serve the monitoring UI."""
    ui_path = os.path.join(os.path.dirname(__file__), "..", "ui", "monitor.html")
    if os.path.exists(ui_path):
        return FileResponse(ui_path, media_type="text/html")
    return HTMLResponse(content="<h1>Monitor UI not found. Please ensure ui/monitor.html exists.</h1>", status_code=404)


@monitor_router.get("/stream")
async def monitor_stream(request: Request):
    """SSE endpoint for real-time message streaming."""
    async def event_generator():
        # Create a queue for this subscriber
        queue = asyncio.Queue()
        monitoring_service.subscribers.append(asyncio.create_task(queue_consumer(queue)))
        
        async def queue_consumer(q):
            while True:
                await q.get()
        
        try:
            # Send initial connection message
            yield f"data: {json.dumps({'type': 'connected', 'timestamp': datetime.now().isoformat()})}\n\n"
            
            # Keep connection alive and send any queued messages
            while True:
                if await request.is_disconnected():
                    break
                
                try:
                    # Send a heartbeat every 30 seconds
                    await asyncio.sleep(30)
                    yield f": heartbeat\n\n"
                except asyncio.CancelledError:
                    break
                    
        finally:
            # Cleanup
            monitoring_service.subscribers = [
                sub for sub in monitoring_service.subscribers 
                if sub != asyncio.current_task()
            ]
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@monitor_router.get("/agents")
async def get_active_agents():
    """Get list of active agents."""
    return list(monitoring_service.active_agents.values())


@monitor_router.get("/messages")
async def get_messages(
    limit: int = 100,
    type: Optional[str] = None
):
    """Get recent messages."""
    return monitoring_service.get_messages(limit=limit, message_type=type)


@monitor_router.get("/stats")
async def get_stats():
    """Get monitoring statistics."""
    return monitoring_service.get_stats()


@monitor_router.post("/intervene")
async def send_intervention(intervention: InterventionRequest):
    """Send a human intervention to an agent."""
    try:
        result = await monitoring_service.handle_intervention(
            agent_id=intervention.agent_id,
            message=intervention.message
        )
        return {
            "success": True,
            "intervention": result
        }
    except Exception as e:
        logger.error(f"Error handling intervention: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@monitor_router.get("/export/json")
async def export_json(limit: int = 1000):
    """Export messages as JSON."""
    messages = monitoring_service.get_messages(limit=limit)
    return {
        "export_date": datetime.now().isoformat(),
        "message_count": len(messages),
        "stats": monitoring_service.get_stats(),
        "messages": messages
    }


@monitor_router.get("/export/csv")
async def export_csv(limit: int = 1000):
    """Export messages as CSV."""
    messages = monitoring_service.get_messages(limit=limit)
    
    # Create CSV content
    csv_lines = ["Timestamp,Type,Agent,Content,Response Time,Tokens,Error"]
    
    for msg in messages:
        timestamp = msg.get("timestamp", "")
        msg_type = msg.get("type", "")
        agent = msg.get("agent_name", "")
        content = str(msg.get("content", "")).replace('"', '""')
        response_time = msg.get("response_time", "")
        tokens = msg.get("tokens", "")
        error = msg.get("error", "")
        
        csv_lines.append(f'"{timestamp}","{msg_type}","{agent}","{content}","{response_time}","{tokens}","{error}"')
    
    csv_content = "\n".join(csv_lines)
    
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=a2a-logs-{datetime.now().timestamp()}.csv"}
    )


# Helper function to integrate monitoring with existing A2A server
async def log_agent_message(agent_name: str, message: str, **kwargs):
    """Helper function to log agent messages."""
    await monitoring_service.log_message(
        agent_name=agent_name,
        content=message,
        **kwargs
    )


# Export the monitoring service and router
__all__ = ["monitor_router", "monitoring_service", "log_agent_message"]
