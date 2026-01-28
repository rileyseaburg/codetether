import { Hono } from "hono"
import { describeRoute, validator, resolver } from "hono-openapi"
import z from "zod"
import { Session } from "../../session"
import { SessionPrompt } from "../../session/prompt"
import { Log } from "../../util/log"
import { errors } from "../error"
import { lazy } from "../../util/lazy"
import { sendTaskCompletionEmail, isEmailConfigured } from "../../util/email"
import { Storage } from "../../storage/storage"
import { PostgresStorage } from "../../storage/postgres-storage"
import { MessageV2 } from "../../session/message-v2"
import { 
  getTenantEmailConfig, 
  isTenantEmailAvailable,
  incrementEmailCount,
  TenantEmailConfig 
} from "../../util/tenant-email"

const log = Log.create({ service: "cloudevent" })

// Model can be either a string like "provider/model" or an object
const ModelSchema = z.union([
  z.string().transform((s) => {
    const [providerID, ...rest] = s.split("/")
    return { providerID, modelID: rest.join("/") }
  }),
  z.object({
    providerID: z.string(),
    modelID: z.string(),
  }),
])

// CloudEvent task data schema
const CloudEventTaskData = z.object({
  task_id: z.string(),
  session_id: z.string(),
  prompt: z.string(),
  agent: z.string().optional(),
  model: ModelSchema.optional(),
  notify_email: z.string().email().optional(),
  title: z.string().optional(),
})
type CloudEventTaskData = z.infer<typeof CloudEventTaskData>

// CloudEvent headers schema
const CloudEventHeaders = z.object({
  "ce-specversion": z.string().default("1.0"),
  "ce-type": z.string(),
  "ce-source": z.string(),
  "ce-id": z.string(),
  "ce-session": z.string().optional(),
})

export const CloudEventRoutes = lazy(() =>
  new Hono().post(
    "/",
    describeRoute({
      summary: "Receive CloudEvent task",
      description:
        "Receive a CloudEvent from Knative Broker containing task data to execute via SessionPrompt.",
      operationId: "cloudevent.task",
      responses: {
        200: {
          description: "Task executed successfully",
          content: {
            "application/json": {
              schema: resolver(
                z.object({
                  success: z.boolean(),
                  task_id: z.string(),
                  session_id: z.string(),
                }),
              ),
            },
          },
        },
        ...errors(400, 404, 500),
      },
    }),
    validator("json", CloudEventTaskData),
    async (c) => {
      // Parse CloudEvent headers
      const ceType = c.req.header("ce-type")
      const ceSource = c.req.header("ce-source")
      const ceId = c.req.header("ce-id")
      const ceSession = c.req.header("ce-session")
      const ceTenant = c.req.header("ce-tenant")

      log.info("received cloudevent", {
        type: ceType,
        source: ceSource,
        id: ceId,
        session: ceSession,
        tenant: ceTenant,
      })
      
      // Initialize PostgresStorage if needed
      try {
        await PostgresStorage.init()
      } catch (e) {
        log.warn("failed to init postgres storage", { error: String(e) })
      }
      
      // Set tenant context if provided (for multi-tenant RLS)
      const tenantId = ceTenant || 'default'
      if (tenantId && tenantId !== 'default') {
        try {
          await PostgresStorage.execute(
            `SELECT set_config('app.current_tenant_id', $1, false)`,
            [tenantId]
          )
          log.info("set tenant context", { tenantId })
        } catch (e) {
          log.warn("failed to set tenant context", { tenantId, error: String(e) })
        }
      }

      // Validate CloudEvent type
      if (ceType !== "codetether.task.created") {
        log.warn("unsupported cloudevent type", { type: ceType })
        return c.json({ error: `Unsupported CloudEvent type: ${ceType}` }, 400)
      }

      const body = c.req.valid("json")
      const sessionID = body.session_id || ceSession

      if (!sessionID) {
        log.error("missing session_id", { body, ceSession })
        return c.json({ error: "session_id is required" }, 400)
      }

      const startTime = Date.now()
      let taskStatus: 'completed' | 'failed' = 'completed'
      let taskError: string | undefined
      let messageId: string | undefined
      
      try {
        // Get or create session
        let session: Session.Info
        let actualSessionID = sessionID
        try {
          session = await Session.get(sessionID)
          log.info("using existing session", { sessionID })
        } catch {
          // Session doesn't exist, create a new one
          session = await Session.create({})
          actualSessionID = session.id
          log.info("created new session", { 
            requestedSessionID: sessionID, 
            actualSessionID 
          })
        }

        // Build prompt parts
        const parts: SessionPrompt.PromptInput["parts"] = [
          {
            type: "text",
            text: body.prompt,
          },
        ]

        // Map agent name - "code" is an alias for "build" (the default coding agent)
        const agentName = body.agent === "code" ? "build" : body.agent

        // Execute task via SessionPrompt
        log.info("executing task", {
          task_id: body.task_id,
          sessionID: actualSessionID,
          agent: agentName,
          model: body.model,
        })

        const result = await SessionPrompt.prompt({
          sessionID: actualSessionID,
          parts,
          agent: agentName,
          model: body.model,
        })

        messageId = result.info.id
        
        log.info("task completed", {
          task_id: body.task_id,
          sessionID: actualSessionID,
          messageID: result.info.id,
        })

        // Send email notification if configured (fire and forget - don't await)
        // Check both global config and tenant-specific config
        const tenantIdForEmail = tenantId
        const hasGlobalConfig = isEmailConfigured()
        
        if (body.notify_email && (hasGlobalConfig || await isTenantEmailAvailable(tenantIdForEmail))) {
          const runtimeSeconds = Math.floor((Date.now() - startTime) / 1000)
          const taskId = body.task_id
          const title = body.title || body.prompt.substring(0, 100)
          const notifyEmail = body.notify_email
          const sessionIdForEmail = actualSessionID
          const messageIdForEmail = messageId
          const resultForEmail = result
          
          // Run email sending asynchronously without blocking or affecting task status
          setTimeout(async () => {
            try {
              // Wait for stream to complete
              await new Promise(resolve => setTimeout(resolve, 2000))
              
              // Get tenant email config if available
              let tenantEmailConfig: TenantEmailConfig | null = null
              try {
                const tenantSettings = await getTenantEmailConfig(tenantIdForEmail)
                if (tenantSettings && tenantSettings.enabled) {
                  tenantEmailConfig = tenantSettings.config
                  // Check quota
                  const quotaExceeded = await isEmailQuotaExceeded(tenantIdForEmail)
                  if (quotaExceeded) {
                    log.warn("tenant email quota exceeded", { tenantId: tenantIdForEmail })
                    return
                  }
                }
              } catch (e) {
                log.warn("failed to get tenant email config, using global", { 
                  tenantId: tenantIdForEmail, 
                  error: String(e) 
                })
              }
              
              // Get the completed message from storage
              let resultText = ''
              try {
                const messageKeys = await Storage.list(["message", sessionIdForEmail])
                
                for (const key of messageKeys) {
                  const msg = await Storage.read<MessageV2.Info>(key)
                  if (msg.id === messageIdForEmail && msg.role === 'assistant') {
                    // Get parts for this message
                    const partKeys = await Storage.list(["part", msg.id])
                    const parts: MessageV2.Part[] = []
                    
                    for (const partKey of partKeys) {
                      const part = await Storage.read<MessageV2.Part>(partKey)
                      parts.push(part)
                    }
                    
                    // Extract text from parts
                    resultText = parts
                      .filter((p: any) => p.type === 'text')
                      .map((p: any) => ('text' in p ? p.text : ''))
                      .join('\n')
                    
                    break
                  }
                }
                
                // Fallback to original result
                if (!resultText && resultForEmail.parts && Array.isArray(resultForEmail.parts)) {
                  resultText = resultForEmail.parts
                    .filter((p: any) => p.type === 'text')
                    .map((p: any) => p.text || '')
                    .join('\n')
                }
              } catch (e) {
                log.warn("failed to get message content for email", { error: String(e) })
              }
              
              // Send email with tenant config if available
              const emailSent = await sendTaskCompletionEmail({
                toEmail: notifyEmail,
                taskId: taskId,
                title: title,
                status: 'completed',
                result: resultText || '(No output captured)',
                runtimeSeconds,
                sessionId: sessionIdForEmail,
              })
            } catch (e) {
              log.error("failed to send completion email", { error: String(e) })
            }
          }, 0)
        }

        // Return 204 No Content for Knative Eventing compatibility
        // Knative expects either empty response or CloudEvent response
        return c.body(null, 204)
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error)
        taskStatus = 'failed'
        taskError = message
        
        log.error("task execution failed", {
          task_id: body.task_id,
          sessionID,
          error: message,
        })
        
        // Send failure email if configured (fire and forget)
        if (body.notify_email && isEmailConfigured()) {
          const runtimeSeconds = Math.floor((Date.now() - startTime) / 1000)
          const notifyEmail = body.notify_email
          const taskId = body.task_id
          const title = body.title || body.prompt.substring(0, 100)
          const errorMsg = taskError
          const sessionIdForEmail = sessionID
          
          setTimeout(async () => {
            try {
              await sendTaskCompletionEmail({
                toEmail: notifyEmail,
                taskId: taskId,
                title: title,
                status: 'failed',
                error: errorMsg,
                runtimeSeconds,
                sessionId: sessionIdForEmail,
              })
            } catch (e) {
              log.error("failed to send failure email", { error: String(e) })
            }
          }, 0)
        }

        // Return 500 with empty body for Knative compatibility
        // The error is already logged above
        return c.body(null, 500)
      }
    },
  ),
)
