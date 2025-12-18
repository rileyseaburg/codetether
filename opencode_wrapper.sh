#!/bin/bash
# Wrapper to run OpenCode from source
cd /home/riley/A2A-Server-MCP/opencode/packages/opencode
exec bun run dev "$@" > /home/riley/A2A-Server-MCP/opencode_debug.log 2>&1
