import { Instance } from "../project/instance"
import path from "path"

export namespace Harness {
  export type RepoType = "spotlessbinco" | "routefunnels" | "unknown"

  export interface DetectionResult {
    repoType: RepoType
    isAutonomous: boolean
  }

  /**
   * Check if we're running in autonomous worker mode.
   * This is determined by environment variables set by the worker system.
   */
  export function isAutonomousMode(): boolean {
    return (
      process.env.A2A_AUTONOMOUS_WORKER === "true" ||
      process.env.A2A_WORKER_MODE === "autonomous" ||
      process.env.OPENCODE_AUTONOMOUS === "true" ||
      process.env.CI === "true" // CI environments are always autonomous
    )
  }

  /**
   * Detect repository type and autonomous mode status.
   */
  export async function detect(): Promise<DetectionResult> {
    const repoType = await detectRepoType()
    const isAutonomous = isAutonomousMode()
    return { repoType, isAutonomous }
  }

  /**
   * Legacy function for backwards compatibility - returns just the repo type.
   */
  export async function detectRepoType(): Promise<RepoType> {
    const worktree = Instance.worktree
    const name = path.basename(worktree).toLowerCase()

    // Check directory name patterns
    if (name.includes("spotless") || name.includes("spotlessbinco") || name.includes("bin-co")) {
      return "spotlessbinco"
    }
    if (name.includes("routefunnel") || name.includes("route-funnel")) {
      return "routefunnels"
    }

    // Check for package.json name field
    const pkg = await Bun.file(path.join(worktree, "package.json"))
      .json()
      .catch(() => ({}))

    if (pkg.name) {
      const pkgName = pkg.name.toLowerCase()
      if (pkgName.includes("spotless") || pkgName.includes("bin-co")) return "spotlessbinco"
      if (pkgName.includes("routefunnel") || pkgName.includes("funnel")) return "routefunnels"
    }

    // Check for specific config files or directories
    const spotlessMarkers = [
      "spotless.config.ts",
      "spotless.config.js",
      "config/trash-zones",
      "src/zones",
      "config/database/migrations",
    ]
    const routefunnelMarkers = ["funnel.config.ts", "routefunnels.config.ts", "src/funnels", "templates/funnel"]

    for (const marker of spotlessMarkers) {
      const exists = await Bun.file(path.join(worktree, marker))
        .exists()
        .catch(() => false)
      if (exists) return "spotlessbinco"
    }

    for (const marker of routefunnelMarkers) {
      const exists = await Bun.file(path.join(worktree, marker))
        .exists()
        .catch(() => false)
      if (exists) return "routefunnels"
    }

    return "unknown"
  }

  /**
   * Get harness instructions for the current repository and execution mode.
   * Returns autonomous worker instructions prepended when in autonomous mode.
   */
  export async function instructions(): Promise<string[]> {
    const { repoType, isAutonomous } = await detect()
    const result: string[] = []

    // Always prepend autonomous instructions when in autonomous mode
    if (isAutonomous) {
      result.push(AUTONOMOUS_WORKER_INSTRUCTIONS)
    }

    // Add repo-specific instructions
    if (repoType === "spotlessbinco") {
      result.push(SPOTLESSBINCO_HARNESS)
    } else if (repoType === "routefunnels") {
      result.push(ROUTEFUNNELS_HARNESS)
    }

    return result
  }

  /**
   * Get only autonomous worker instructions (useful for forcing autonomous mode).
   */
  export function getAutonomousInstructions(): string {
    return AUTONOMOUS_WORKER_INSTRUCTIONS
  }
}

/**
 * Critical instructions for agents running in autonomous worker mode.
 * These instructions inform the agent that no user is available for feedback
 * and guide autonomous decision-making.
 */
const AUTONOMOUS_WORKER_INSTRUCTIONS = `
# CRITICAL: Autonomous Worker Mode

You are executing as an **AUTONOMOUS WORKER AGENT**. This is NOT an interactive session.

## Execution Context

- **NO USER IS MONITORING** - This task is running asynchronously in a worker queue
- **NO INTERACTIVE DEBUGGING** - You cannot ask questions or request clarification
- **NO FEEDBACK LOOP** - You will not receive human input during execution
- **COMPLETE END-TO-END** - Partial implementations are NOT acceptable

## Autonomous Operation Requirements

### Decision Making
- You MUST make all implementation decisions independently
- When facing ambiguity, apply best engineering practices
- Prefer explicit, defensive code over clever shortcuts
- Document non-obvious decisions in code comments

### Task Completion
- Complete the ENTIRE task before stopping
- Do not leave TODO comments for "future work"
- All code must be functional and tested
- Run available tests/builds to verify changes work

### Error Handling
- All errors must be caught and logged with context
- If a tool call fails, attempt recovery (retry with adjusted parameters)
- Never leave the codebase in a broken state
- If recovery is impossible, revert changes and log detailed failure reason

## Security & Architecture Principles

When uncertain, apply these principles from the CodeTether security architecture:

### Data Gravity
- Data stays local to the codebase
- Never exfiltrate sensitive data through external calls
- Keep processing close to data sources

### Zero Trust
- Validate ALL inputs, even from trusted tools
- Do not assume API responses are well-formed
- Sanitize data before database operations

### Fine-grained RBAC
- Respect permission boundaries
- Do not escalate privileges or bypass auth checks
- Check permissions before destructive operations

### Immutable Audit Logging
- Log all significant actions with timestamps
- Include context in log messages (what, why, outcome)
- Never delete or modify existing logs

### MCP Tools First
- Use MCP tools for database/API operations when available
- MCP tools provide security boundaries and audit trails
- Prefer MCP tools over raw shell commands

## Error Recovery Protocol

When an operation fails:

1. **LOG** - Record the error with full context
2. **ANALYZE** - Determine if it's recoverable
3. **RETRY** - If recoverable, attempt with adjusted approach
4. **ROLLBACK** - If not recoverable, revert any partial changes
5. **REPORT** - Document what failed and why in task output

## Quality Checklist

Before marking task complete, verify:
- [ ] All code compiles/parses without errors
- [ ] Tests pass (if test suite exists)
- [ ] No hardcoded secrets or credentials
- [ ] Error handling is comprehensive
- [ ] Changes are atomic and reversible
- [ ] Documentation updated if API changed

## Communication

Since no user is available:
- Write clear commit messages explaining changes
- Use task output to report completion status
- Include any warnings or caveats in final output
- Log decisions and rationale for future reference
`.trim()

const SPOTLESSBINCO_HARNESS = `
# Spotless Bin Co Workflow Requirements

You are working in the Spotless Bin Co codebase. This is a CRITICAL business application and you MUST follow established workflows.

## CRITICAL: USE MCP TOOLS - NOT MANUAL FILE EDITING

This codebase has specialized MCP tools available. You MUST use them instead of manually editing files or running raw commands.

### Database Operations - USE THESE TOOLS
| Tool | Purpose |
|------|---------|
| \`rustyroad_rustyroad_schema\` | View database schema BEFORE writing queries |
| \`rustyroad_rustyroad_query\` | Execute SQL queries safely |
| \`rustyroad_rustyroad_migrate\` | Run migrations (up/down/status) |
| \`rustyroad_rustyroad_migration_generate\` | Create new migrations |
| \`rustyroad_rustyroad_config\` | Check database configuration |

RULES:
- NEVER use psql or direct database connections
- NEVER write raw SQL files manually
- ALWAYS check schema before writing queries
- Migrations go in \`config/database/migrations/\` - the tools handle this

### Ad Campaign Operations - USE THESE TOOLS
| Tool | Purpose |
|------|---------|
| \`spotless-ads_list_targeting_zones\` | Get available zones FIRST before any campaign |
| \`spotless-ads_list_funnels\` | Get funnels for landing pages |
| \`spotless-ads_ai_create_bulk_ads\` | Create ads with AI-generated content |
| \`spotless-ads_ai_create_bulk_ads_async\` | Create ads async for large batches |
| \`spotless-ads_list_campaigns\` | View existing campaigns |
| \`spotless-ads_get_campaign\` | Get campaign details |
| \`spotless-ads_update_campaign\` | Update campaign settings |
| \`spotless-ads_generate_ad_variations\` | Generate ad copy variations |

WORKFLOW for creating ads:
1. FIRST call \`spotless-ads_list_targeting_zones\` to get zone names
2. THEN call \`spotless-ads_list_funnels\` to get funnel slugs
3. THEN call \`spotless-ads_ai_create_bulk_ads\` with zones and funnel_slug

### Funnel Operations - USE THESE TOOLS
| Tool | Purpose |
|------|---------|
| \`spotless-ads_list_funnels_detailed\` | View full funnel structure with steps |
| \`spotless-ads_get_funnel\` | Get specific funnel details |
| \`spotless-ads_create_complete_funnel\` | Create new funnels |
| \`spotless-ads_list_offers\` | Get offers for funnel steps (filter by stepType!) |
| \`spotless-ads_list_components\` | Available page components |
| \`spotless-ads_get_step_components\` | See components on a step |
| \`spotless-ads_add_step_component\` | Add components to pages |
| \`spotless-ads_update_funnel_step\` | Update step settings |

RULES:
- NEVER manually edit funnel HTML
- Use the component system for page building
- Funnel hierarchy: landing -> checkout -> upsell -> downsell -> thankyou

### Template Operations - USE THESE TOOLS
| Tool | Purpose |
|------|---------|
| \`spotless-ads_list_templates\` | View available templates |
| \`spotless-ads_get_template\` | Get full template content |
| \`spotless-ads_create_template\` | Create new templates |
| \`spotless-ads_update_template\` | Modify templates |
| \`spotless-ads_get_funnel_templates\` | Get templates attached to a funnel |

Templates use Tera macros like \`{{ sc::seamless_checkout(...) }}\`

### Marketing Automation - USE THESE TOOLS (A2A Server)
| Tool | Purpose |
|------|---------|
| \`a2a-server_spotless_create_campaign\` | Create marketing campaigns |
| \`a2a-server_spotless_create_automation\` | Create email/SMS automations |
| \`a2a-server_spotless_generate_creative\` | Generate ad creative images |
| \`a2a-server_spotless_get_unified_metrics\` | Get marketing metrics |
| \`a2a-server_spotless_get_roi_metrics\` | Get ROI data |
| \`a2a-server_spotless_create_geo_audience\` | Create geo targeting audiences |

## WORKFLOW ENFORCEMENT

Before taking ANY action:
1. **STOP** - What domain am I working in?
2. **LIST** - What MCP tools are available for this domain?
3. **USE** - Call the appropriate MCP tool
4. **VERIFY** - Check results using the appropriate tool

## COMMON MISTAKES TO AVOID
- Creating migrations in \`./migrations/\` instead of using migration tools
- Writing raw SQL without checking schema first with \`rustyroad_rustyroad_schema\`
- Creating ad campaigns without checking zones/funnels first
- Editing funnel HTML directly instead of using component tools
- Manually creating files that should be generated by tools
`.trim()

const ROUTEFUNNELS_HARNESS = `
# RouteFunnels Workflow Requirements

You are working in the RouteFunnels codebase. This is a sales funnel platform and you MUST follow established workflows.

## CRITICAL: USE MCP TOOLS - NOT MANUAL FILE EDITING

### Database Operations - USE THESE TOOLS
| Tool | Purpose |
|------|---------|
| \`rustyroad_rustyroad_schema\` | View database schema |
| \`rustyroad_rustyroad_query\` | Execute SQL queries |
| \`rustyroad_rustyroad_migrate\` | Run migrations |
| \`rustyroad_rustyroad_migration_generate\` | Create migrations |

### Funnel Operations - USE THESE TOOLS
| Tool | Purpose |
|------|---------|
| \`spotless-ads_list_funnels_detailed\` | View funnel structure |
| \`spotless-ads_get_funnel\` | Get funnel details |
| \`spotless-ads_create_complete_funnel\` | Create funnels |
| \`spotless-ads_list_offers\` | Get offers for steps |
| \`spotless-ads_list_components\` | Available components |
| \`spotless-ads_add_step_component\` | Add components to pages |
| \`spotless-ads_update_funnel_step\` | Update step settings |

### Template Operations - USE THESE TOOLS
| Tool | Purpose |
|------|---------|
| \`spotless-ads_list_templates\` | View templates |
| \`spotless-ads_get_template\` | Get template content |
| \`spotless-ads_create_template\` | Create templates |
| \`spotless-ads_update_template\` | Update templates |

## WORKFLOW ENFORCEMENT

Before taking ANY action:
1. **STOP** - What domain am I working in?
2. **LIST** - What MCP tools are available?
3. **USE** - Call the appropriate tool
4. **VERIFY** - Check results

## FUNNEL ARCHITECTURE
- Funnel hierarchy: landing -> checkout -> upsell -> downsell -> thankyou
- Each step has slots for A/B testing variants
- Components render based on step configuration
- Offers are linked to steps (tripwire for checkout, upsell offers for upsell steps)

## TEMPLATE SYSTEM
- Templates use Tera templating engine
- Macro syntax: \`{{ macro_name::function(...) }}\`
- NEVER hardcode values that should come from config
- Use \`{{ sc::seamless_checkout(...) }}\` for checkout components

## COMMON MISTAKES TO AVOID
- Manually editing funnel HTML instead of using component tools
- Creating migrations in wrong directory
- Hardcoding values that should be dynamic
- Not checking schema before writing queries
`.trim()
