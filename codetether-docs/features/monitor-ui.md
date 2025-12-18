---
title: Monitor UI
description: Web dashboard for agent monitoring
---

# Monitor UI

CodeTether includes a web-based monitoring dashboard.

## Access

Open in your browser:

```
http://localhost:8000/v1/monitor/

# Or, if you run the MCP HTTP server separately:
http://localhost:9000/v1/monitor/
```

## Features

- **Agent Status** - View connected agents
- **Live Messages** - Real-time message stream
- **Task Queue** - Pending and running tasks
- **Statistics** - Usage metrics

## Authentication

When Keycloak is enabled, the dashboard requires authentication.
