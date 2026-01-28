import z from "zod"
import { Tool } from "./tool"
import { Log } from "../util/log"
import { RalphLoop } from "../ralph/ralph-loop"
import { RalphA2A } from "../ralph/ralph-a2a"
import { RalphRlm } from "../ralph/ralph-rlm"
import { Instance } from "../project/instance"
import path from "path"
import fs from "fs/promises"

const log = Log.create({ service: "ralph-tool" })

const DESCRIPTION = `Run the Ralph autonomous agent loop to implement user stories from a PRD.

Ralph is an autonomous AI agent loop that runs repeatedly until all PRD items are complete.
Each iteration is a fresh instance with clean context. Memory persists via:
- Git history (commits from previous iterations)
- progress.txt (learnings and context)
- prd.json (which stories are done)

Use this when you have:
- A prd.json file with user stories to implement
- Want to automate multi-step feature development
- Need to run "while true" style autonomous coding

Based on Geoffrey Huntley's Ralph pattern: while :; do cat PROMPT.md | opencode; done

Examples:
- ralph({ action: "run" }) - Start Ralph loop with default prd.json
- ralph({ action: "status" }) - Check progress of current Ralph run
- ralph({ action: "create-prd", feature: "user auth" }) - Create a new PRD
- ralph({ action: "distributed", maxParallel: 3 }) - Run via A2A workers
`

interface RalphResult {
  title: string
  metadata: Record<string, unknown>
  output: string
}

export const RalphTool = Tool.define("ralph", async () => {
  return {
    description: DESCRIPTION,
    parameters: z.object({
      action: z
        .enum(["run", "status", "create-prd", "convert-prd", "distributed", "compress-progress"])
        .describe("Action to perform"),
      prdPath: z.string().optional().describe("Path to prd.json file (default: prd.json)"),
      feature: z.string().optional().describe("Feature description for create-prd action"),
      maxIterations: z.number().optional().describe("Maximum iterations for run action (default: 10)"),
      maxParallel: z.number().optional().describe("Max parallel workers for distributed action (default: 3)"),
      sequential: z.boolean().optional().describe("Run stories sequentially in distributed mode"),
    }),
    async execute(params, ctx): Promise<RalphResult> {
      const prdPath = params.prdPath || "prd.json"

      switch (params.action) {
        case "run": {
          ctx.metadata({
            title: "Ralph Loop Starting...",
            metadata: { prdPath, maxIterations: params.maxIterations || 10 },
          })

          try {
            const state = await RalphLoop.run(
              {
                prdPath,
                maxIterations: params.maxIterations || 10,
              },
              ctx.abort,
            )

            const passedCount = state.prd.userStories.filter((s) => s.passes).length
            const totalCount = state.prd.userStories.length

            return {
              title: `Ralph ${state.status === "completed" ? "Complete" : "Stopped"}`,
              metadata: {
                status: state.status,
                iterations: state.currentIteration,
                passed: passedCount,
                total: totalCount,
                project: state.prd.project,
                branch: state.prd.branchName,
              },
              output: `# Ralph ${state.status === "completed" ? "Complete!" : "Stopped"}

**Project:** ${state.prd.project}
**Branch:** ${state.prd.branchName}
**Progress:** ${passedCount}/${totalCount} stories passed
**Iterations:** ${state.currentIteration}/${state.maxIterations}

## Stories
${state.prd.userStories.map((s) => `- [${s.passes ? "x" : " "}] ${s.id}: ${s.title}`).join("\n")}

## Progress Log
${state.progressLog.slice(-5).map((p) => `- ${p.storyId}: ${p.status}`).join("\n")}
`,
            }
          } catch (e: unknown) {
            const message = e instanceof Error ? e.message : String(e)
            return {
              title: "Ralph Failed",
              metadata: { error: message },
              output: `Ralph loop failed: ${message}`,
            }
          }
        }

        case "status": {
          try {
            const prd = await RalphLoop.loadPRD(prdPath)
            const progress = await RalphLoop.readProgress("progress.txt")
            const passedCount = prd.userStories.filter((s) => s.passes).length

            return {
              title: `Ralph Status: ${passedCount}/${prd.userStories.length}`,
              metadata: {
                project: prd.project,
                branch: prd.branchName,
                passed: passedCount,
                total: prd.userStories.length,
              },
              output: `# Ralph Status

**Project:** ${prd.project}
**Branch:** ${prd.branchName}
**Progress:** ${passedCount}/${prd.userStories.length} stories

## Stories
${prd.userStories.map((s) => `- [${s.passes ? "x" : " "}] ${s.id}: ${s.title}`).join("\n")}

## Recent Progress
${progress.split("---").slice(-3).join("\n---\n")}
`,
            }
          } catch (e: unknown) {
            const message = e instanceof Error ? e.message : String(e)
            return {
              title: "No Ralph PRD Found",
              metadata: { error: message },
              output: `No prd.json found at ${prdPath}. Create one with: ralph({ action: "create-prd", feature: "your feature" })`,
            }
          }
        }

        case "create-prd": {
          if (!params.feature) {
            return {
              title: "Feature Required",
              metadata: { error: "missing feature" },
              output: 'Please provide a feature description: ralph({ action: "create-prd", feature: "your feature" })',
            }
          }

          // Create tasks directory if needed
          await fs.mkdir(path.join(Instance.directory, "tasks"), { recursive: true })

          // Generate PRD filename
          const kebabName = params.feature
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, "-")
            .replace(/^-|-$/g, "")
          const prdFilePath = path.join(Instance.directory, "tasks", `prd-${kebabName}.md`)

          return {
            title: "PRD Creation Helper",
            metadata: { feature: params.feature, prdPath: prdFilePath },
            output: `# Create PRD for: ${params.feature}

To create a PRD, load the 'prd' skill and follow its instructions:

\`\`\`
/skill prd

Create a PRD for: ${params.feature}
\`\`\`

The skill will:
1. Ask clarifying questions
2. Generate a structured PRD
3. Save to tasks/prd-${kebabName}.md

After creating the PRD, convert it to Ralph format:
\`\`\`
ralph({ action: "convert-prd" })
\`\`\`
`,
          }
        }

        case "convert-prd": {
          return {
            title: "Convert PRD to Ralph Format",
            metadata: {},
            output: `# Convert PRD to prd.json

To convert an existing PRD to Ralph format, load the 'ralph' skill:

\`\`\`
/skill ralph

Convert the PRD in tasks/prd-*.md to prd.json
\`\`\`

The skill will:
1. Parse the PRD markdown
2. Extract user stories
3. Create prd.json with proper structure
4. Archive any existing prd.json if from a different feature

After conversion, run Ralph:
\`\`\`
ralph({ action: "run" })
\`\`\`
`,
          }
        }

        case "distributed": {
          const a2aConfig = await RalphA2A.getConfig()
          if (!a2aConfig) {
            return {
              title: "A2A Not Configured",
              metadata: { error: "missing config" },
              output: `A2A server not configured. Set these environment variables:
- A2A_SERVER_URL: The A2A server URL (e.g., https://api.codetether.run)
- A2A_AUTH_TOKEN: Your auth token
`,
            }
          }

          ctx.metadata({
            title: "Ralph Distributed Starting...",
            metadata: { prdPath, maxParallel: params.maxParallel || 3, sequential: params.sequential },
          })

          try {
            const state = await RalphA2A.runDistributed(prdPath, a2aConfig, {
              maxParallel: params.maxParallel || 3,
              sequential: params.sequential,
            })

            const passedCount = state.prd.userStories.filter((s) => s.passes).length

            return {
              title: `Ralph Distributed ${state.status === "completed" ? "Complete" : "Stopped"}`,
              metadata: {
                status: state.status,
                passed: passedCount,
                total: state.prd.userStories.length,
              },
              output: `# Ralph Distributed ${state.status === "completed" ? "Complete!" : "Stopped"}

**Project:** ${state.prd.project}
**Progress:** ${passedCount}/${state.prd.userStories.length} stories
**Mode:** ${params.sequential ? "Sequential" : `Parallel (max ${params.maxParallel || 3})`}

## Stories
${state.prd.userStories.map((s) => `- [${s.passes ? "x" : " "}] ${s.id}: ${s.title}`).join("\n")}
`,
            }
          } catch (e: unknown) {
            const message = e instanceof Error ? e.message : String(e)
            return {
              title: "Ralph Distributed Failed",
              metadata: { error: message },
              output: `Distributed execution failed: ${message}`,
            }
          }
        }

        case "compress-progress": {
          try {
            const prd = await RalphLoop.loadPRD(prdPath)
            const progress = await RalphLoop.readProgress("progress.txt")

            const result = await RalphRlm.compressProgress(progress, prd, {
              sessionID: ctx.sessionID,
              abort: ctx.abort,
            })

            // Save compressed progress
            const progressPath = path.join(Instance.directory, "progress.txt")
            await fs.writeFile(progressPath, result.compressed)

            return {
              title: `Progress Compressed (${result.ratio.toFixed(1)}x)`,
              metadata: {
                originalTokens: result.originalTokens,
                compressedTokens: result.compressedTokens,
                ratio: result.ratio,
              },
              output: `# Progress Compressed

**Original:** ${result.originalTokens.toLocaleString()} tokens
**Compressed:** ${result.compressedTokens.toLocaleString()} tokens
**Ratio:** ${result.ratio.toFixed(1)}x

The progress.txt file has been compressed while preserving key learnings.
`,
            }
          } catch (e: unknown) {
            const message = e instanceof Error ? e.message : String(e)
            return {
              title: "Compression Failed",
              metadata: { error: message },
              output: `Failed to compress progress: ${message}`,
            }
          }
        }

        default:
          return {
            title: "Unknown Action",
            metadata: {},
            output: `Unknown action: ${params.action}. Valid actions: run, status, create-prd, convert-prd, distributed, compress-progress`,
          }
      }
    },
  }
})
