import type { APIEvent } from "@solidjs/start/server"
import { Database, desc, eq } from "@opencode-ai/console-core/drizzle/index.js"
import { BenchmarkTable } from "@opencode-ai/console-core/schema/benchmark.sql.js"
import { KeyTable } from "@opencode-ai/console-core/schema/key.sql.js"
import { Identifier } from "@opencode-ai/console-core/identifier.js"

interface SubmissionBody {
  model: string
  agent: string
  result: string
}

async function authenticateRequest(event: APIEvent): Promise<boolean> {
  const authHeader = event.request.headers.get("authorization")
  if (!authHeader?.startsWith("Bearer ")) return false
  const token = authHeader.slice(7)
  const rows = await Database.use((tx) =>
    tx.select({ id: KeyTable.id }).from(KeyTable).where(eq(KeyTable.key, token)).limit(1),
  )
  return rows.length > 0
}

export async function GET(event: APIEvent) {
  const url = new URL(event.request.url)
  const model = url.searchParams.get("model")
  const agent = url.searchParams.get("agent")
  const limitParam = url.searchParams.get("limit")
  const limit = Math.min(Math.max(parseInt(limitParam ?? "50", 10) || 50, 1), 200)

  let query = Database.use((tx) => {
    let q = tx.select().from(BenchmarkTable).orderBy(desc(BenchmarkTable.timeCreated)).limit(limit)
    if (model) q = q.where(eq(BenchmarkTable.model, model)) as typeof q
    if (agent) q = q.where(eq(BenchmarkTable.agent, agent)) as typeof q
    return q
  })

  const rows = await query

  return Response.json({
    count: rows.length,
    results: rows.map((row) => ({
      id: row.id,
      model: row.model,
      agent: row.agent,
      result: JSON.parse(row.result),
      timeCreated: row.timeCreated,
    })),
  })
}

export async function POST(event: APIEvent) {
  const authenticated = await authenticateRequest(event)
  if (!authenticated) {
    return Response.json({ error: "Unauthorized" }, { status: 401 })
  }

  const body = (await event.request.json()) as SubmissionBody

  if (!body.model || !body.agent || !body.result) {
    return Response.json({ error: "All fields are required" }, { status: 400 })
  }

  await Database.use((tx) =>
    tx.insert(BenchmarkTable).values({
      id: Identifier.create("benchmark"),
      model: body.model,
      agent: body.agent,
      result: body.result,
    }),
  )

  return Response.json({ success: true }, { status: 200 })
}
