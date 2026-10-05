#!/usr/bin/env python3
"""
A2A CLI Client

A command-line interface for interacting with A2A protocol agents.
"""

import asyncio
import json
import sys
from typing import Optional, Dict, Any
import argparse

import httpx
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from a2a_server.models import JSONRPCRequest, Message, Part


class A2AClient:
    """Client for communicating with A2A agents."""
    
    def __init__(self, base_url: str, auth_token: Optional[str] = None):
        self.base_url = base_url.rstrip('/')
        self.auth_token = auth_token
        self.client = httpx.AsyncClient()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for requests."""
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers
    
    async def get_agent_card(self) -> Optional[Dict[str, Any]]:
        """Fetch the agent card."""
        try:
            response = await self.client.get(
                f"{self.base_url}/.well-known/agent-card.json"
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching agent card: {e}")
            return None
    
    async def send_message(self, content: str, task_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Send a message to the agent."""
        message = Message(parts=[Part(type="text", content=content)])
        
        request = JSONRPCRequest(
            method="message/send",
            params={
                "message": message.model_dump(),
                "task_id": task_id
            },
            id="1"
        )
        
        try:
            response = await self.client.post(
                self.base_url,
                json=request.model_dump(),
                headers=self._get_headers()
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error sending message: {e}")
            return None
    
    async def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task information."""
        request = JSONRPCRequest(
            method="tasks/get",
            params={"task_id": task_id},
            id="1"
        )
        
        try:
            response = await self.client.post(
                self.base_url,
                json=request.model_dump(),
                headers=self._get_headers()
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error getting task: {e}")
            return None
    
    async def cancel_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Cancel a task."""
        request = JSONRPCRequest(
            method="tasks/cancel",
            params={"task_id": task_id},
            id="1"
        )
        
        try:
            response = await self.client.post(
                self.base_url,
                json=request.model_dump(),
                headers=self._get_headers()
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error cancelling task: {e}")
            return None
    
    async def stream_message(self, content: str, task_id: Optional[str] = None):
        """Send a message with streaming response."""
        message = Message(parts=[Part(type="text", content=content)])
        
        request = JSONRPCRequest(
            method="message/stream",
            params={
                "message": message.model_dump(),
                "task_id": task_id
            },
            id="1"
        )
        
        try:
            async with self.client.stream(
                "POST",
                self.base_url,
                json=request.model_dump(),
                headers=self._get_headers()
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]  # Remove "data: " prefix
                        if data.strip():
                            try:
                                event = json.loads(data)
                                yield event
                            except json.JSONDecodeError:
                                continue
        except Exception as e:
            print(f"Error streaming message: {e}")


async def interactive_mode(client: A2AClient):
    """Interactive chat mode."""
    print("=== A2A Interactive Mode ===")
    print("Type 'exit' to quit, 'help' for commands")
    print()
    
    # Fetch and display agent card
    agent_card = await client.get_agent_card()
    if agent_card:
        print(f"Connected to: {agent_card['name']}")
        print(f"Description: {agent_card['description']}")
        print()
        
        if agent_card.get('skills'):
            print("Available skills:")
            for skill in agent_card['skills']:
                print(f"  - {skill['name']}: {skill['description']}")
            print()
    
    current_task_id = None
    
    while True:
        try:
            user_input = input("> ").strip()
            
            if user_input.lower() in ['exit', 'quit']:
                break
            elif user_input.lower() == 'help':
                print("Commands:")
                print("  help - Show this help")
                print("  info - Show agent information")
                print("  stream <message> - Send message with streaming")
                print("  task <task_id> - Get task information")
                print("  cancel <task_id> - Cancel a task")
                print("  exit - Quit")
                print("  Or just type a message to send it")
                continue
            elif user_input.lower() == 'info':
                if agent_card:
                    print(json.dumps(agent_card, indent=2))
                continue
            elif user_input.startswith('stream '):
                message = user_input[7:]
                print(f"Streaming: {message}")
                async for event in client.stream_message(message):
                    if 'result' in event and 'event' in event['result']:
                        task_event = event['result']['event']
                        task = task_event['task']
                        print(f"Task {task['id']}: {task['status']}")
                        if task_event.get('message'):
                            msg = task_event['message']
                            for part in msg['parts']:
                                if part['type'] == 'text':
                                    print(f"Response: {part['content']}")
                        if task_event.get('final'):
                            print("(Final)")
                continue
            elif user_input.startswith('task '):
                task_id = user_input[5:]
                result = await client.get_task(task_id)
                if result:
                    print(json.dumps(result, indent=2))
                continue
            elif user_input.startswith('cancel '):
                task_id = user_input[7:]
                result = await client.cancel_task(task_id)
                if result:
                    print(f"Cancelled task: {task_id}")
                continue
            elif not user_input:
                continue
            
            # Send regular message
            result = await client.send_message(user_input, current_task_id)
            if result and 'result' in result:
                response = result['result']
                if 'task' in response:
                    task = response['task']
                    current_task_id = task['id']
                    print(f"Task: {task['id']} ({task['status']})")
                
                if 'message' in response and response['message']:
                    message = response['message']
                    for part in message['parts']:
                        if part['type'] == 'text':
                            print(f"Response: {part['content']}")
            elif result and 'error' in result:
                error = result['error']
                print(f"Error: {error['message']}")
        
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except EOFError:
            break


async def main():
    parser = argparse.ArgumentParser(description="A2A CLI Client")
    parser.add_argument("url", help="Base URL of the A2A agent")
    parser.add_argument("--auth", help="Authentication token")
    parser.add_argument("--message", help="Send a single message and exit")
    parser.add_argument("--stream", action="store_true", help="Use streaming for the message")
    parser.add_argument("--info", action="store_true", help="Show agent information and exit")
    
    args = parser.parse_args()
    
    async with A2AClient(args.url, args.auth) as client:
        if args.info:
            agent_card = await client.get_agent_card()
            if agent_card:
                print(json.dumps(agent_card, indent=2))
            return
        
        if args.message:
            if args.stream:
                print(f"Streaming: {args.message}")
                async for event in client.stream_message(args.message):
                    if 'result' in event and 'event' in event['result']:
                        task_event = event['result']['event']
                        if task_event.get('message'):
                            msg = task_event['message']
                            for part in msg['parts']:
                                if part['type'] == 'text':
                                    print(part['content'])
            else:
                result = await client.send_message(args.message)
                if result and 'result' in result:
                    response = result['result']
                    if 'message' in response and response['message']:
                        message = response['message']
                        for part in message['parts']:
                            if part['type'] == 'text':
                                print(part['content'])
                elif result and 'error' in result:
                    error = result['error']
                    print(f"Error: {error['message']}")
            return
        
        # Interactive mode
        await interactive_mode(client)


if __name__ == "__main__":
    asyncio.run(main())