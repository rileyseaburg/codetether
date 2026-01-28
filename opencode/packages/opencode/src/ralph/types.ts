import z from "zod"

/**
 * Ralph PRD Schema Types
 * Based on the Ralph autonomous agent pattern by Geoffrey Huntley
 */

export namespace RalphTypes {
  export const UserStory = z.object({
    id: z.string(),
    title: z.string(),
    description: z.string(),
    acceptanceCriteria: z.array(z.string()),
    priority: z.number(),
    passes: z.boolean(),
    notes: z.string().optional(),
  })
  export type UserStory = z.infer<typeof UserStory>

  export const PRD = z.object({
    project: z.string(),
    branchName: z.string(),
    description: z.string(),
    userStories: z.array(UserStory),
  })
  export type PRD = z.infer<typeof PRD>

  export const ProgressEntry = z.object({
    timestamp: z.string(),
    storyId: z.string(),
    status: z.enum(["started", "completed", "failed", "skipped"]),
    notes: z.string().optional(),
    iteration: z.number().optional(),
  })
  export type ProgressEntry = z.infer<typeof ProgressEntry>

  export const RalphState = z.object({
    prd: PRD,
    currentIteration: z.number(),
    maxIterations: z.number(),
    progressLog: z.array(ProgressEntry),
    startedAt: z.string(),
    lastUpdatedAt: z.string(),
    status: z.enum(["running", "completed", "failed", "paused"]),
    branchCreated: z.boolean().optional(),
  })
  export type RalphState = z.infer<typeof RalphState>

  export interface IterationResult {
    storyId: string
    success: boolean
    notes: string
    commitHash?: string
    duration: number
  }

  export interface RalphConfig {
    prdPath: string
    progressPath: string
    maxIterations: number
    checkCommand?: string
    branchPrefix: string
    archiveDir: string
    // RLM integration
    useRlmCompression: boolean
    rlmThreshold: number // Compress when context exceeds this token count
    // A2A integration
    a2aServerUrl?: string
    a2aAuthToken?: string
    createA2ATasks: boolean
  }
}
