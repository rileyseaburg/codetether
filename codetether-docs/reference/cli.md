---
title: CLI Reference
description: CodeTether CLI command reference
---

# CLI Reference

CodeTether command-line interface.

## Commands

### serve

Start the server:

```bash
codetether serve --port 8000
```

`serve` is a friendly alias for starting a single server instance.

### run

Explicit form of starting a single server:

```bash
codetether run --port 8000
```

### codetether-worker

Start a worker:

```bash
codetether-worker --server https://example.com --name worker-1 --codebase /path/to/repo
```

### version

Show version:

```bash
codetether --version
```
