import asyncio
import aiohttp
import json
import sys

async def verify_models():
    base_url = "https://api.codetether.run"
    codebase_id = "e06584eb"  # Global workspace ID (prod)

    async with aiohttp.ClientSession() as session:
        # 1. Get available models
        print(f"Fetching models from {base_url}/v1/opencode/models...")
        async with session.get(f"{base_url}/v1/opencode/models") as resp:
            if resp.status != 200:
                print(f"Error fetching models: {resp.status}")
                print(await resp.text())
                return

            models_data = await resp.json()
            models = models_data.get("models", [])

        if not models:
            print("No models found in the database. Make sure the worker is registered and reporting models.")
            return

        print(f"Found {len(models)} models: {[m['id'] for m in models]}")

        # 2. Trigger a message for each model
        for model_info in models:
            model_id = model_info["id"]
            print(f"\n--- Testing model: {model_id} ---")

            payload = {
                "prompt": f"Hello from test script! This is a connectivity test for model {model_id}.",
                "agent": "build",
                "model": model_id
            }

            trigger_url = f"{base_url}/v1/opencode/codebases/{codebase_id}/trigger"
            print(f"Triggering agent at {trigger_url}...")

            async with session.post(trigger_url, json=payload) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    task_id = result.get('session_id') or result.get('task_id')
                    print(f"Success! Task created: {task_id}")

                    if task_id:
                        # Poll for completion
                        print(f"Waiting for task {task_id} to complete...")
                        while True:
                            async with session.get(f"{base_url}/v1/opencode/tasks/{task_id}") as task_resp:
                                if task_resp.status == 200:
                                    task_data = await task_resp.json()
                                    status = task_data.get("status")
                                    print(f"Status: {status}")

                                    if status in ["completed", "failed", "cancelled"]:
                                        print(f"Task finished with status: {status}")
                                        if status == "completed":
                                            print(f"Result: {task_data.get('result')}")
                                        elif status == "failed":
                                            print(f"Error: {task_data.get('error')}")
                                        break
                                else:
                                    print(f"Error checking task status: {task_resp.status}")
                                    break

                            await asyncio.sleep(2)
                else:
                    print(f"Failed to trigger model {model_id}: {resp.status}")
                    print(await resp.text())

if __name__ == "__main__":
    try:
        asyncio.run(verify_models())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
