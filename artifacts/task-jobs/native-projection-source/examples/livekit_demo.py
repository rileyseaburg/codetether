#!/usr/bin/env python3
"""
LiveKit Demo for A2A Server

This demo script shows how to use the LiveKit integration in the A2A server
to create and manage real-time media sessions.
"""

import asyncio
import os
import json
import httpx
from typing import Dict, Any

# Demo configuration
A2A_SERVER_URL = "http://localhost:8000"
DEMO_ROOM_NAME = "demo-room"
DEMO_USER_IDENTITY = "demo-user"


async def demo_livekit_integration():
    """Demonstrate LiveKit integration with A2A server."""
    print("🎥 LiveKit Integration Demo")
    print("=" * 50)
    
    # Check if server is running
    print("1. Checking A2A server...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{A2A_SERVER_URL}/health")
            if response.status_code == 200:
                print("   ✅ A2A server is running")
            else:
                print(f"   ❌ A2A server returned {response.status_code}")
                return
        except Exception as e:
            print(f"   ❌ Cannot connect to A2A server: {e}")
            print(f"   Please start the server with: python run_server.py run --enhanced")
            return
    
    # Get agent card to check media capabilities
    print("\n2. Checking agent capabilities...")
    try:
        response = await client.get(f"{A2A_SERVER_URL}/.well-known/agent-card.json")
        agent_card = response.json()
        
        has_media = agent_card.get("capabilities", {}).get("media", False)
        has_livekit = agent_card.get("additional_interfaces", {}).get("livekit") is not None
        
        print(f"   Media capability: {'✅' if has_media else '❌'}")
        print(f"   LiveKit interface: {'✅' if has_livekit else '❌'}")
        
        if has_livekit:
            livekit_config = agent_card["additional_interfaces"]["livekit"]
            print(f"   Token endpoint: {livekit_config.get('token_endpoint', 'N/A')}")
            print(f"   Server managed: {livekit_config.get('server_managed', 'N/A')}")
        
    except Exception as e:
        print(f"   ❌ Failed to get agent card: {e}")
        return
    
    # Test media session creation via agent message
    print("\n3. Testing media session creation...")
    try:
        message_payload = {
            "jsonrpc": "2.0",
            "method": "message/send",
            "params": {
                "message": {
                    "parts": [
                        {
                            "type": "text",
                            "content": f"create media session room {DEMO_ROOM_NAME} as {DEMO_USER_IDENTITY}"
                        }
                    ]
                }
            },
            "id": "demo-1"
        }
        
        response = await client.post(
            A2A_SERVER_URL,
            json=message_payload,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            if "error" in result:
                print(f"   ❌ Agent error: {result['error']}")
            else:
                print("   ✅ Media session request sent successfully")
                
                # Extract response from the message
                if "result" in result:
                    message_result = result["result"]
                    if "message" in message_result and message_result["message"]["parts"]:
                        for part in message_result["message"]["parts"]:
                            if part["type"] == "text":
                                print(f"   Response: {part['content']}")
                            elif part["type"] == "data":
                                print("   📊 Session data received:")
                                session_data = part["content"]
                                print(f"      Room: {session_data.get('room_name', 'N/A')}")
                                print(f"      Identity: {session_data.get('participant_identity', 'N/A')}")
                                print(f"      Role: {session_data.get('role', 'N/A')}")
                                print(f"      Join URL: {session_data.get('join_url', 'N/A')}")
        else:
            print(f"   ❌ HTTP error: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Failed to create media session: {e}")
    
    # Test direct token endpoint (if LiveKit is configured)
    print("\n4. Testing direct token endpoint...")
    
    # Check if LiveKit environment variables are set
    livekit_configured = bool(os.getenv("LIVEKIT_API_KEY") and os.getenv("LIVEKIT_API_SECRET"))
    
    if not livekit_configured:
        print("   ⚠️  LiveKit not configured (missing LIVEKIT_API_KEY/LIVEKIT_API_SECRET)")
        print("   This is expected in demo mode. To test with real LiveKit:")
        print("   export LIVEKIT_API_KEY=your_api_key")
        print("   export LIVEKIT_API_SECRET=your_api_secret")
        print("   export LIVEKIT_URL=https://your-livekit-server.com")
    else:
        try:
            token_payload = {
                "room_name": DEMO_ROOM_NAME,
                "identity": DEMO_USER_IDENTITY,
                "role": "participant",
                "ttl_minutes": 60
            }
            
            response = await client.post(
                f"{A2A_SERVER_URL}/v1/livekit/token",
                json=token_payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                token_data = response.json()
                print("   ✅ Token generated successfully")
                print(f"   Join URL: {token_data.get('join_url', 'N/A')}")
                print(f"   Expires: {token_data.get('expires_at', 'N/A')}")
            elif response.status_code == 401:
                print("   ⚠️  Authentication required for direct token endpoint")
            elif response.status_code == 503:
                print("   ⚠️  LiveKit bridge not configured")
            else:
                print(f"   ❌ Failed to get token: {response.status_code}")
                
        except Exception as e:
            print(f"   ❌ Token request failed: {e}")
    
    # Test joining existing room
    print("\n5. Testing room joining...")
    try:
        join_message = {
            "jsonrpc": "2.0",
            "method": "message/send",
            "params": {
                "message": {
                    "parts": [
                        {
                            "type": "text",
                            "content": f"join room {DEMO_ROOM_NAME} as viewer-{DEMO_USER_IDENTITY}"
                        }
                    ]
                }
            },
            "id": "demo-2"
        }
        
        response = await client.post(
            A2A_SERVER_URL,
            json=join_message,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            if "error" in result:
                print(f"   ❌ Agent error: {result['error']}")
            else:
                print("   ✅ Room join request sent successfully")
                
                # Extract response
                if "result" in result:
                    message_result = result["result"]
                    if "message" in message_result and message_result["message"]["parts"]:
                        for part in message_result["message"]["parts"]:
                            if part["type"] == "text":
                                print(f"   Response: {part['content']}")
        else:
            print(f"   ❌ HTTP error: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Failed to join room: {e}")
    
    # Test agent help
    print("\n6. Testing agent help...")
    try:
        help_message = {
            "jsonrpc": "2.0",
            "method": "message/send",
            "params": {
                "message": {
                    "parts": [
                        {
                            "type": "text",
                            "content": "help with media"
                        }
                    ]
                }
            },
            "id": "demo-3"
        }
        
        response = await client.post(
            A2A_SERVER_URL,
            json=help_message,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            if "result" in result:
                message_result = result["result"]
                if "message" in message_result and message_result["message"]["parts"]:
                    for part in message_result["message"]["parts"]:
                        if part["type"] == "text":
                            print(f"   Help text: {part['content']}")
        
    except Exception as e:
        print(f"   ❌ Failed to get help: {e}")
    
    print("\n🎉 Demo completed!")
    print("\nNext steps:")
    print("1. Configure LiveKit server and credentials")
    print("2. Create a frontend client to use the join URLs")
    print("3. Test real-time audio/video functionality")


async def demo_streaming_session():
    """Demonstrate streaming media session updates."""
    print("\n📡 Streaming Demo")
    print("=" * 30)
    
    async with httpx.AsyncClient() as client:
        try:
            # Start a streaming session for media creation
            stream_message = {
                "jsonrpc": "2.0",
                "method": "message/stream",
                "params": {
                    "message": {
                        "parts": [
                            {
                                "type": "text",
                                "content": f"create media session room streaming-demo as stream-user"
                            }
                        ]
                    }
                },
                "id": "stream-demo-1"
            }
            
            print("Starting streaming session...")
            
            # Note: In a real implementation, this would use Server-Sent Events
            # For now, we'll just show the concept
            response = await client.post(
                f"{A2A_SERVER_URL}/",
                json=stream_message,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                print("✅ Streaming session initiated")
                print(f"Task ID: {result.get('result', {}).get('task', {}).get('id', 'N/A')}")
            else:
                print(f"❌ Failed to start streaming: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Streaming demo failed: {e}")


async def main():
    """Run the complete demo."""
    print("🚀 A2A LiveKit Integration Demo")
    print("This demo shows the LiveKit media integration features.")
    print()
    
    await demo_livekit_integration()
    await demo_streaming_session()
    
    print("\n" + "=" * 70)
    print("Demo completed! Check the A2A server logs for detailed information.")


if __name__ == "__main__":
    # Run the demo
    asyncio.run(main())