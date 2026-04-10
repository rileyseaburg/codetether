# CodeTether Benchmark Suite

Standardized benchmark PRDs for evaluating autonomous coding agents using Ralph's PRD-driven development loop.

## How It Works

Each benchmark is a PRD (Product Requirements Document) containing user stories with acceptance criteria and quality gates. The benchmark runner:

1. Clones a scaffold project into an isolated worktree
2. Executes the Ralph loop against the PRD with a specified model
3. Records pass rates, timing, token usage, and cost per story
4. Submits results to the benchmark API

## Tiers

| Tier | Stories | Description |
|------|---------|-------------|
| **Tier 1 (Simple)** | 1-2 | Single-file tasks — functions, unit tests, basic CRUD |
| **Tier 2 (Medium)** | 3-5 | Multi-file tasks with dependencies — APIs, data models, integration |
| **Tier 3 (Complex)** | 8-15 | Full features with parallel stages — multi-module, refactors, quality gates |

## Running Benchmarks

```bash
# Run all benchmarks with a specific model
codetether benchmark --prd-dir benchmarks/ --models anthropic:claude-sonnet-4-20250514

# Run a single tier
codetether benchmark --prd-dir benchmarks/ --tier 1 --models openai:o3

# Run with multiple models for comparison
codetether benchmark --prd-dir benchmarks/ --models anthropic:claude-sonnet-4-20250514,openai:o3,moonshotai:kimi-k2

# Parallel execution across model×PRD combos
codetether benchmark --prd-dir benchmarks/ --models anthropic:claude-sonnet-4-20250514,openai:o3 --parallel
```

## Scaffold Projects

The `scaffolds/` directory contains starter projects that PRDs operate against. Each scaffold provides a minimal codebase with build tooling already configured.

## Results Schema

Results are stored in the agent benchmark table with this structure:

```json
{
  "prd_id": "bench-t1-rest-api",
  "prd_tier": 1,
  "stories_total": 2,
  "stories_passed": 2,
  "pass_rate": 1.0,
  "duration_seconds": 125,
  "tokens_used": 45000,
  "cost_usd": 0.34,
  "quality_checks": [
    { "name": "typecheck", "passed": true },
    { "name": "test", "passed": true },
    { "name": "lint", "passed": true },
    { "name": "build", "passed": true }
  ],
  "per_story": [
    {
      "story_id": "US-001",
      "passed": true,
      "iterations": 1,
      "duration_seconds": 65,
      "tokens_used": 22000,
      "files_changed": ["src/main.rs", "src/lib.rs"]
    }
  ]
}
```
