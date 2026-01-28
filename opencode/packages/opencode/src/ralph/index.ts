/**
 * Ralph - Autonomous PRD-driven Agent Loop
 *
 * Based on Geoffrey Huntley's Ralph pattern:
 * "while :; do cat PROMPT.md | opencode; done"
 *
 * Ralph runs AI coding tools repeatedly until all PRD items are complete.
 * Each iteration is a fresh instance with clean context.
 * Memory persists via git history, progress.txt, and prd.json.
 *
 * Features:
 * - PRD-driven development with user stories
 * - Automatic quality checks (typecheck, tests)
 * - Git branch management and commits
 * - Progress tracking and learnings
 * - RLM integration for context compression
 * - A2A server integration for distributed execution
 *
 * Usage:
 * 1. Create a PRD using the 'prd' skill
 * 2. Convert to prd.json using the 'ralph' skill
 * 3. Run: ralph({ action: "run" })
 *
 * Or with A2A distributed workers:
 * ralph({ action: "distributed", maxParallel: 3 })
 */

export { RalphTypes } from "./types"
export { RalphLoop } from "./ralph-loop"
export { RalphA2A } from "./ralph-a2a"
export { RalphRlm } from "./ralph-rlm"
