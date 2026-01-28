import { spawn } from "child_process"
import fs from "fs/promises"
import path from "path"
import { Log } from "../util/log"
import { Instance } from "../project/instance"
import { RalphTypes } from "./types"
import { Bus } from "../bus"
import { BusEvent } from "../bus/bus-event"
import z from "zod"

const log = Log.create({ service: "ralph-loop" })

/**
 * Ralph Loop - Autonomous PRD-driven agent execution
 *
 * Based on Geoffrey Huntley's Ralph pattern:
 * while :; do cat PROMPT.md | opencode; done
 *
 * Each iteration:
 * 1. Reads prd.json to find next incomplete story
 * 2. Spawns fresh OpenCode instance with clean context
 * 3. Passes the story as a prompt
 * 4. Runs quality checks (typecheck, tests)
 * 5. If checks pass, commits and marks story complete
 * 6. Appends learnings to progress.txt
 * 7. Repeats until all stories pass or max iterations reached
 *
 * Memory persists via:
 * - Git history (commits from previous iterations)
 * - progress.txt (learnings and context)
 * - prd.json (which stories are done)
 */
export namespace RalphLoop {
  // Events for UI/monitoring
  export const Event = {
    Started: BusEvent.define(
      "ralph.started",
      z.object({
        project: z.string(),
        branchName: z.string(),
        totalStories: z.number(),
        maxIterations: z.number(),
      }),
    ),
    IterationStarted: BusEvent.define(
      "ralph.iteration.started",
      z.object({
        iteration: z.number(),
        maxIterations: z.number(),
        storyId: z.string(),
        storyTitle: z.string(),
      }),
    ),
    IterationCompleted: BusEvent.define(
      "ralph.iteration.completed",
      z.object({
        iteration: z.number(),
        storyId: z.string(),
        success: z.boolean(),
        commitHash: z.string().optional(),
        duration: z.number(),
      }),
    ),
    StoryPassed: BusEvent.define(
      "ralph.story.passed",
      z.object({
        storyId: z.string(),
        storyTitle: z.string(),
        remainingStories: z.number(),
      }),
    ),
    Completed: BusEvent.define(
      "ralph.completed",
      z.object({
        project: z.string(),
        totalIterations: z.number(),
        passedStories: z.number(),
        totalStories: z.number(),
        duration: z.number(),
      }),
    ),
    Failed: BusEvent.define(
      "ralph.failed",
      z.object({
        iteration: z.number(),
        storyId: z.string().optional(),
        error: z.string(),
      }),
    ),
  }

  const DEFAULT_CONFIG: RalphTypes.RalphConfig = {
    prdPath: "prd.json",
    progressPath: "progress.txt",
    maxIterations: 10,
    checkCommand: "npm run typecheck || npx tsc --noEmit",
    branchPrefix: "ralph/",
    archiveDir: ".ralph/archive",
    useRlmCompression: true,
    rlmThreshold: 80000,
    createA2ATasks: false,
  }

  /**
   * Load PRD from file
   */
  export async function loadPRD(prdPath: string): Promise<RalphTypes.PRD> {
    const fullPath = path.isAbsolute(prdPath) ? prdPath : path.join(Instance.directory, prdPath)
    const content = await fs.readFile(fullPath, "utf-8")
    const data = JSON.parse(content)
    return RalphTypes.PRD.parse(data)
  }

  /**
   * Save PRD to file
   */
  export async function savePRD(prd: RalphTypes.PRD, prdPath: string): Promise<void> {
    const fullPath = path.isAbsolute(prdPath) ? prdPath : path.join(Instance.directory, prdPath)
    await fs.writeFile(fullPath, JSON.stringify(prd, null, 2))
  }

  /**
   * Get next incomplete story (lowest priority that hasn't passed)
   */
  export function getNextStory(prd: RalphTypes.PRD): RalphTypes.UserStory | null {
    const incomplete = prd.userStories.filter((s) => !s.passes).sort((a, b) => a.priority - b.priority)
    return incomplete[0] || null
  }

  /**
   * Build the prompt for a single story iteration
   */
  export function buildStoryPrompt(
    story: RalphTypes.UserStory,
    prd: RalphTypes.PRD,
    progress: string,
    iteration: number,
  ): string {
    const completedStories = prd.userStories.filter((s) => s.passes)
    const remainingStories = prd.userStories.filter((s) => !s.passes && s.id !== story.id)

    return `# Ralph Iteration ${iteration}

## Project: ${prd.project}
## Branch: ${prd.branchName}
## Feature: ${prd.description}

---

## Your Task: ${story.id} - ${story.title}

${story.description}

### Acceptance Criteria
${story.acceptanceCriteria.map((c, i) => `${i + 1}. ${c}`).join("\n")}

---

## Context

### Completed Stories (${completedStories.length}/${prd.userStories.length})
${completedStories.length > 0 ? completedStories.map((s) => `- [x] ${s.id}: ${s.title}`).join("\n") : "(none yet)"}

### Remaining After This (${remainingStories.length})
${remainingStories.length > 0 ? remainingStories.map((s) => `- [ ] ${s.id}: ${s.title}`).join("\n") : "(this is the last story!)"}

### Previous Learnings
${progress || "(none yet)"}

---

## Instructions

1. **Implement ONLY this story** - don't work on other stories
2. **Run quality checks** after implementation:
   - \`npm run typecheck\` or \`npx tsc --noEmit\`
   - Run tests if applicable
3. **Commit your changes** with a clear message: "feat(${story.id}): ${story.title}"
4. **Report your findings** - what worked, what didn't, gotchas discovered
5. If ALL acceptance criteria pass, output: \`<promise>STORY_COMPLETE</promise>\`
6. If you cannot complete the story, output: \`<promise>STORY_BLOCKED: [reason]</promise>\`

## Important
- Each iteration is a FRESH context - I don't remember previous iterations
- Use git history and progress.txt for context
- Be specific in your learnings - they help future iterations
- COMMIT your work before finishing
`
  }

  /**
   * Append to progress.txt
   */
  export async function appendProgress(progressPath: string, entry: string): Promise<void> {
    const fullPath = path.isAbsolute(progressPath) ? progressPath : path.join(Instance.directory, progressPath)

    try {
      await fs.access(fullPath)
    } catch {
      // Create initial progress file
      const header = `# Ralph Progress Log
# Started: ${new Date().toISOString()}

## Learnings
`
      await fs.writeFile(fullPath, header)
    }

    await fs.appendFile(fullPath, `\n---\n${new Date().toISOString()}\n${entry}\n`)
  }

  /**
   * Read progress.txt
   */
  export async function readProgress(progressPath: string): Promise<string> {
    const fullPath = path.isAbsolute(progressPath) ? progressPath : path.join(Instance.directory, progressPath)
    try {
      return await fs.readFile(fullPath, "utf-8")
    } catch {
      return ""
    }
  }

  /**
   * Run quality check command
   */
  export async function runCheck(command: string): Promise<{ success: boolean; output: string }> {
    return new Promise((resolve) => {
      const proc = spawn("sh", ["-c", command], {
        cwd: Instance.directory,
        stdio: ["ignore", "pipe", "pipe"],
      })

      let stdout = ""
      let stderr = ""

      proc.stdout?.on("data", (d) => (stdout += d.toString()))
      proc.stderr?.on("data", (d) => (stderr += d.toString()))

      proc.on("close", (code) => {
        resolve({
          success: code === 0,
          output: stdout + stderr,
        })
      })

      proc.on("error", (err) => {
        resolve({
          success: false,
          output: err.message,
        })
      })
    })
  }

  /**
   * Create git branch if needed
   */
  export async function ensureBranch(branchName: string): Promise<void> {
    const { success: onBranch } = await runCheck(`git rev-parse --abbrev-ref HEAD | grep -q "^${branchName}$"`)
    if (onBranch) return

    // Check if branch exists
    const { success: branchExists } = await runCheck(`git show-ref --verify --quiet refs/heads/${branchName}`)

    if (branchExists) {
      await runCheck(`git checkout ${branchName}`)
    } else {
      await runCheck(`git checkout -b ${branchName}`)
    }
  }

  /**
   * Commit changes
   */
  export async function commitChanges(message: string): Promise<string | null> {
    // Stage all changes
    await runCheck("git add -A")

    // Check if there are changes to commit
    const { success: hasChanges } = await runCheck("git diff --cached --quiet")
    if (hasChanges) {
      // No changes (diff --quiet returns 0 if no changes)
      return null
    }

    // Commit
    const { success, output } = await runCheck(`git commit -m "${message.replace(/"/g, '\\"')}"`)
    if (!success) {
      log.warn("Commit failed", { output })
      return null
    }

    // Get commit hash
    const { output: hash } = await runCheck("git rev-parse --short HEAD")
    return hash.trim()
  }

  /**
   * Run a single iteration
   */
  export async function runIteration(
    story: RalphTypes.UserStory,
    prd: RalphTypes.PRD,
    config: RalphTypes.RalphConfig,
    iteration: number,
    abort: AbortSignal,
  ): Promise<RalphTypes.IterationResult> {
    const startTime = Date.now()
    log.info("Starting Ralph iteration", { iteration, storyId: story.id, storyTitle: story.title })

    Bus.publish(Event.IterationStarted, {
      iteration,
      maxIterations: config.maxIterations,
      storyId: story.id,
      storyTitle: story.title,
    })

    const progress = await readProgress(config.progressPath)
    const prompt = buildStoryPrompt(story, prd, progress, iteration)

    // Spawn OpenCode with the prompt
    // Using headless mode with --print flag
    const result = await new Promise<{ success: boolean; output: string; commitHash?: string }>((resolve) => {
      const args = ["--print", "--dangerously-skip-permissions"]
      const proc = spawn("opencode", args, {
        cwd: Instance.directory,
        stdio: ["pipe", "pipe", "pipe"],
        env: {
          ...process.env,
          OPENCODE_RALPH_MODE: "1",
          OPENCODE_MAX_TURNS: "50",
        },
      })

      let stdout = ""
      let stderr = ""

      proc.stdout?.on("data", (d) => (stdout += d.toString()))
      proc.stderr?.on("data", (d) => (stderr += d.toString()))

      // Send prompt to stdin
      proc.stdin?.write(prompt)
      proc.stdin?.end()

      const timeout = setTimeout(() => {
        proc.kill()
        resolve({ success: false, output: "Iteration timed out after 10 minutes" })
      }, 600000) // 10 minute timeout

      abort.addEventListener("abort", () => {
        clearTimeout(timeout)
        proc.kill()
        resolve({ success: false, output: "Iteration aborted" })
      })

      proc.on("close", async (code) => {
        clearTimeout(timeout)

        // Check for success markers in output
        const storyComplete = stdout.includes("<promise>STORY_COMPLETE</promise>")
        const storyBlocked = stdout.match(/<promise>STORY_BLOCKED:\s*(.+?)<\/promise>/)

        if (storyBlocked) {
          resolve({
            success: false,
            output: `Story blocked: ${storyBlocked[1]}`,
          })
          return
        }

        // Run quality checks
        if (config.checkCommand) {
          const check = await runCheck(config.checkCommand)
          if (!check.success) {
            resolve({
              success: false,
              output: `Quality check failed:\n${check.output}`,
            })
            return
          }
        }

        // If we got here, try to commit
        const commitHash = await commitChanges(`feat(${story.id}): ${story.title}`)

        resolve({
          success: storyComplete || code === 0,
          output: stdout,
          commitHash: commitHash || undefined,
        })
      })

      proc.on("error", (err) => {
        clearTimeout(timeout)
        resolve({ success: false, output: err.message })
      })
    })

    const duration = Date.now() - startTime

    // Extract learnings from output
    const learnings = extractLearnings(result.output, story.id, result.success)
    await appendProgress(config.progressPath, learnings)

    Bus.publish(Event.IterationCompleted, {
      iteration,
      storyId: story.id,
      success: result.success,
      commitHash: result.commitHash,
      duration,
    })

    return {
      storyId: story.id,
      success: result.success,
      notes: learnings,
      commitHash: result.commitHash,
      duration,
    }
  }

  /**
   * Extract learnings from iteration output
   */
  function extractLearnings(output: string, storyId: string, success: boolean): string {
    const lines = [`### ${storyId} - ${success ? "PASSED" : "FAILED"}`]

    // Look for explicit learnings
    const learningsMatch = output.match(/## Learnings\n([\s\S]*?)(?=\n##|$)/)
    if (learningsMatch) {
      lines.push(learningsMatch[1].trim())
    }

    // Look for errors
    if (!success) {
      const errorMatch = output.match(/Error:.*$/m)
      if (errorMatch) {
        lines.push(`Error: ${errorMatch[0]}`)
      }
    }

    // Truncate to reasonable size
    const result = lines.join("\n")
    return result.length > 2000 ? result.slice(0, 2000) + "..." : result
  }

  /**
   * Main loop - run until all stories pass or max iterations reached
   */
  export async function run(
    config: Partial<RalphTypes.RalphConfig> = {},
    abort: AbortSignal = new AbortController().signal,
  ): Promise<RalphTypes.RalphState> {
    const fullConfig = { ...DEFAULT_CONFIG, ...config }
    const startTime = Date.now()

    // Load PRD
    const prd = await loadPRD(fullConfig.prdPath)
    log.info("Ralph starting", {
      project: prd.project,
      branch: prd.branchName,
      stories: prd.userStories.length,
      maxIterations: fullConfig.maxIterations,
    })

    Bus.publish(Event.Started, {
      project: prd.project,
      branchName: prd.branchName,
      totalStories: prd.userStories.length,
      maxIterations: fullConfig.maxIterations,
    })

    // Create branch
    await ensureBranch(prd.branchName)

    const state: RalphTypes.RalphState = {
      prd,
      currentIteration: 0,
      maxIterations: fullConfig.maxIterations,
      progressLog: [],
      startedAt: new Date().toISOString(),
      lastUpdatedAt: new Date().toISOString(),
      status: "running",
      branchCreated: true,
    }

    // Main loop
    for (let i = 0; i < fullConfig.maxIterations && !abort.aborted; i++) {
      state.currentIteration = i + 1
      state.lastUpdatedAt = new Date().toISOString()

      // Get next story
      const story = getNextStory(prd)
      if (!story) {
        // All stories complete!
        state.status = "completed"
        break
      }

      // Run iteration
      const result = await runIteration(story, prd, fullConfig, i + 1, abort)

      state.progressLog.push({
        timestamp: new Date().toISOString(),
        storyId: story.id,
        status: result.success ? "completed" : "failed",
        notes: result.notes,
        iteration: i + 1,
      })

      // Update story status
      if (result.success) {
        const storyIndex = prd.userStories.findIndex((s) => s.id === story.id)
        if (storyIndex !== -1) {
          prd.userStories[storyIndex].passes = true
          prd.userStories[storyIndex].notes = result.notes
        }

        // Save updated PRD
        await savePRD(prd, fullConfig.prdPath)

        const remaining = prd.userStories.filter((s) => !s.passes).length
        Bus.publish(Event.StoryPassed, {
          storyId: story.id,
          storyTitle: story.title,
          remainingStories: remaining,
        })

        log.info("Story passed", { storyId: story.id, remaining })
      } else {
        log.warn("Story failed", { storyId: story.id, notes: result.notes })
        // Continue to next iteration - Ralph will retry or try different approach
      }
    }

    // Check final status
    const passedCount = prd.userStories.filter((s) => s.passes).length
    if (passedCount === prd.userStories.length) {
      state.status = "completed"
    } else if (state.currentIteration >= fullConfig.maxIterations) {
      state.status = "failed"
    }

    Bus.publish(Event.Completed, {
      project: prd.project,
      totalIterations: state.currentIteration,
      passedStories: passedCount,
      totalStories: prd.userStories.length,
      duration: Date.now() - startTime,
    })

    log.info("Ralph finished", {
      status: state.status,
      iterations: state.currentIteration,
      passed: passedCount,
      total: prd.userStories.length,
      duration: Date.now() - startTime,
    })

    return state
  }
}
