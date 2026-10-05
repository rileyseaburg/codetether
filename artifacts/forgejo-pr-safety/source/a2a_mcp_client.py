#!/usr/bin/env python3
"""
Standalone MCP client module for connecting to A2A Server from external tools.

This can be used as:
  python -m a2a_mcp_client --endpoint http://localhost:9000/mcp/v1/rpc

Or imported:
  from a2a_mcp_client import A2AMCPClient
"""

import sys
import os

# Add examples directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'examples'))

from mcp_external_client import A2AMCPClient, main

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
