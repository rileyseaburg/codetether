import { Log } from "../util/log"
import { RalphTypes } from "./types"
import { RalphLoop } from "./ralph-loop"

const log = Log.create({ service: "ralph-a2a" })

/**
 * Ralph A2A Integration
 *
 * Connects Ralph loop execution with the A2A server for:
 * 1. Creating tasks for each PRD story
 * 2. Distributing work across multiple workers
 * 3. Monitoring progress via the dashboard
 * 4. Leveraging RLM for context compression in long sessions
 */
export namespace RalphA2A {
  export interface A2AConfig {
    serverUrl: string
    authToken: string
    codebaseId?: string
    notifyEmail?: string
  }

  /**
   * Create an A2A task for a Ralph story
   */
  export async function createStoryTask(
    story: RalphTypes.UserStory,
    prd: RalphTypes.PRD,
    config: A2AConfig,
    iteration: number,
  ): Promise<{ taskId: string; runId: string }> {
    const prompt = RalphLoop.buildStoryPrompt(story, prd, "", iteration)

    const response = await fetch(`${config.serverUrl}/v1/task`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${config.authToken}`,
      },
      body: JSON.stringify({
        title: `Ralph: ${story.id} - ${story.title}`,
        description: prompt,
        agent_type: "build",
        priority: 10 - story.priority, // Higher priority for lower story numbers
        codebase_id: config.codebaseId || "global",
        metadata: {
          ralph: true,
          prdProject: prd.project,
          branchName: prd.branchName,
          storyId: story.id,
          iteration,
        },
        notify_email: config.notifyEmail,
      }),
    })

    if (!response.ok) {
      const error = await response.text()
      throw new Error(`Failed to create A2A task: ${error}`)
    }

    const data = await response.json()
    log.info("Created A2A task for story", {
      taskId: data.task_id,
      storyId: story.id,
      storyTitle: story.title,
    })

    return {
      taskId: data.task_id,
      runId: data.run_id,
    }
  }

  /**
   * Create A2A tasks for all incomplete stories in a PRD
   */
  export async function createAllStoryTasks(
    prd: RalphTypes.PRD,
    config: A2AConfig,
  ): Promise<Array<{ storyId: string; taskId: string; runId: string }>> {
    const results: Array<{ storyId: string; taskId: string; runId: string }> = []
    const incompleteStories = prd.userStories.filter((s) => !s.passes).sort((a, b) => a.priority - b.priority)

    for (let i = 0; i < incompleteStories.length; i++) {
      const story = incompleteStories[i]
      try {
        const task = await createStoryTask(story, prd, config, i + 1)
        results.push({
          storyId: story.id,
          ...task,
        })
      } catch (e: any) {
        log.error("Failed to create task for story", { storyId: story.id, error: e.message })
      }
    }

    return results
  }

  /**
   * Poll for task completion and update PRD
   */
  export async function waitForTaskCompletion(
    taskId: string,
    config: A2AConfig,
    timeoutMs: number = 600000, // 10 minutes default
  ): Promise<{ success: boolean; output: string }> {
    const startTime = Date.now()

    while (Date.now() - startTime < timeoutMs) {
      const response = await fetch(`${config.serverUrl}/v1/task/${taskId}`, {
        headers: {
          Authorization: `Bearer ${config.authToken}`,
        },
      })

      if (!response.ok) {
        throw new Error(`Failed to get task status: ${await response.text()}`)
      }

      const task = await response.json()

      if (task.status === "completed") {
        return {
          success: true,
          output: task.result || "",
        }
      }

      if (task.status === "failed" || task.status === "cancelled") {
        return {
          success: false,
          output: task.error || task.result || "Task failed",
        }
      }

      // Wait before polling again
      await new Promise((r) => setTimeout(r, 5000))
    }

    return {
      success: false,
      output: "Task timed out",
    }
  }

  /**
   * Run Ralph loop via A2A distributed workers
   *
   * This distributes each story to A2A workers instead of running locally,
   * enabling parallel execution and leveraging cloud compute.
   */
  export async function runDistributed(
    prdPath: string,
    config: A2AConfig,
    options: {
      maxParallel?: number
      sequential?: boolean
    } = {},
  ): Promise<RalphTypes.RalphState> {
    const prd = await RalphLoop.loadPRD(prdPath)
    const startTime = Date.now()

    log.info("Starting distributed Ralph execution", {
      project: prd.project,
      stories: prd.userStories.length,
      sequential: options.sequential,
    })

    const state: RalphTypes.RalphState = {
      prd,
      currentIteration: 0,
      maxIterations: prd.userStories.length,
      progressLog: [],
      startedAt: new Date().toISOString(),
      lastUpdatedAt: new Date().toISOString(),
      status: "running",
    }

    if (options.sequential) {
      // Run stories one at a time (like traditional Ralph)
      for (const story of prd.userStories.sort((a, b) => a.priority - b.priority)) {
        if (story.passes) continue

        state.currentIteration++
        const task = await createStoryTask(story, prd, config, state.currentIteration)
        const result = await waitForTaskCompletion(task.taskId, config)

        state.progressLog.push({
          timestamp: new Date().toISOString(),
          storyId: story.id,
          status: result.success ? "completed" : "failed",
          notes: result.output.slice(0, 500),
          iteration: state.currentIteration,
        })

        if (result.success) {
          story.passes = true
          story.notes = result.output.slice(0, 500)
          await RalphLoop.savePRD(prd, prdPath)
        }
      }
    } else {
      // Run stories in parallel (up to maxParallel)
      const maxParallel = options.maxParallel || 3
      const tasks = await createAllStoryTasks(prd, config)

      // Process in batches
      for (let i = 0; i < tasks.length; i += maxParallel) {
        const batch = tasks.slice(i, i + maxParallel)
        const results = await Promise.all(batch.map((t) => waitForTaskCompletion(t.taskId, config)))

        for (let j = 0; j < batch.length; j++) {
          const task = batch[j]
          const result = results[j]
          const story = prd.userStories.find((s) => s.id === task.storyId)

          if (story && result.success) {
            story.passes = true
            story.notes = result.output.slice(0, 500)
          }

          state.progressLog.push({
            timestamp: new Date().toISOString(),
            storyId: task.storyId,
            status: result.success ? "completed" : "failed",
            notes: result.output.slice(0, 500),
            iteration: state.currentIteration,
          })
        }

        state.currentIteration += batch.length
        await RalphLoop.savePRD(prd, prdPath)
      }
    }

    // Final status
    const passedCount = prd.userStories.filter((s) => s.passes).length
    state.status = passedCount === prd.userStories.length ? "completed" : "failed"
    state.lastUpdatedAt = new Date().toISOString()

    log.info("Distributed Ralph execution complete", {
      status: state.status,
      passed: passedCount,
      total: prd.userStories.length,
      duration: Date.now() - startTime,
    })

    return state
  }

  /**
   * Get A2A config from environment/config
   */
  export async function getConfig(): Promise<A2AConfig | null> {
    const serverUrl = process.env.A2A_SERVER_URL
    const authToken = process.env.A2A_AUTH_TOKEN

    if (!serverUrl || !authToken) {
      return null
    }

    return {
      serverUrl,
      authToken,
      codebaseId: process.env.A2A_CODEBASE_ID,
      notifyEmail: process.env.A2A_NOTIFY_EMAIL,
    }
  }
}
