import * as path from 'node:path'
import { randomUUID } from 'node:crypto'
import * as vscode from 'vscode'

type Codebase = {
    id: string
    name?: string
    path?: string
}

type TokenUsage = {
    input?: number
    output?: number
    reasoning?: number
    cache?: {
        read?: number
        write?: number
    }
}

const SESSION_ID_KEY = 'codetetherSessionId'
const SESSION_TITLE_KEY = 'codetetherSessionTitle'
const CODEBASE_ID_STATE_KEY = 'codetetherCodebaseId'

function normalizeFsPath(value: string): string {
    const resolved = path.resolve(value)
    return process.platform === 'win32' ? resolved.toLowerCase() : resolved
}

function getConfig() {
    return vscode.workspace.getConfiguration('codetether')
}

function getApiUrl(): string {
    const url = String(getConfig().get('apiUrl') || '').trim()
    return url || 'http://localhost:8000'
}

function getApiToken(): string | undefined {
    const token = String(getConfig().get('apiToken') || '').trim()
    return token || undefined
}

function getOverrideCodebaseId(): string | undefined {
    const id = String(getConfig().get('codebaseId') || '').trim()
    return id || undefined
}

async function fetchJson(url: string, init?: RequestInit): Promise<any> {
    const res = await fetch(url, init)
    if (!res.ok) {
        const text = await res.text().catch(() => '')
        throw new Error(`HTTP ${res.status}: ${text || res.statusText}`)
    }
    const ct = res.headers.get('content-type') || ''
    if (ct.includes('application/json')) return res.json()
    const raw = await res.text()
    try {
        return JSON.parse(raw)
    } catch {
        return raw
    }
}

async function postJson(url: string, body: unknown, token?: string): Promise<any> {
    const headers: Record<string, string> = {
        'content-type': 'application/json',
    }
    if (token) headers.authorization = `Bearer ${token}`
    return fetchJson(url, {
        method: 'POST',
        headers,
        body: JSON.stringify(body),
    })
}

async function listServerCodebases(apiUrl: string, token?: string): Promise<Codebase[]> {
    const headers: Record<string, string> = {}
    if (token) headers.authorization = `Bearer ${token}`
    const data = await fetchJson(`${apiUrl}/v1/opencode/codebases/list`, { headers })
    const items = Array.isArray(data) ? data : Array.isArray(data?.codebases) ? data.codebases : []
    return (items as any[])
        .map((cb) => ({
            id: String(cb?.id ?? ''),
            name: typeof cb?.name === 'string' ? cb.name : undefined,
            path: typeof cb?.path === 'string' ? cb.path : undefined,
        }))
        .filter((cb) => cb.id)
}

async function pickCodebase(context: vscode.ExtensionContext): Promise<string | undefined> {
    const apiUrl = getApiUrl()
    const token = getApiToken()
    const codebases = await listServerCodebases(apiUrl, token)
    if (!codebases.length) {
        void vscode.window.showWarningMessage('No codebases found on the CodeTether server.')
        return undefined
    }

    const pick = await vscode.window.showQuickPick(
        codebases.map((cb) => ({
            label: cb.name ? `${cb.name} (${cb.id})` : cb.id,
            description: cb.path,
            value: cb.id,
        })),
        { placeHolder: 'Select a CodeTether codebase for this workspace' }
    )
    if (!pick) return undefined
    await context.workspaceState.update(CODEBASE_ID_STATE_KEY, pick.value)
    return pick.value
}

async function resolveCodebaseId(context: vscode.ExtensionContext): Promise<string | undefined> {
    const override = getOverrideCodebaseId()
    if (override) return override

    const stored = context.workspaceState.get<string>(CODEBASE_ID_STATE_KEY)
    if (stored) return stored

    const workspaceFolder = vscode.workspace.workspaceFolders?.[0]
    const workspacePath = workspaceFolder?.uri?.fsPath
    if (!workspacePath) {
        return pickCodebase(context)
    }

    try {
        const apiUrl = getApiUrl()
        const token = getApiToken()
        const codebases = await listServerCodebases(apiUrl, token)
        const target = normalizeFsPath(workspacePath)
        const match = codebases.find((cb) => cb.path && normalizeFsPath(cb.path) === target)
        if (match) {
            await context.workspaceState.update(CODEBASE_ID_STATE_KEY, match.id)
            return match.id
        }
    } catch {
        // ignore and fall back to picker
    }

    return pickCodebase(context)
}

function extractSessionMetadata(history: readonly (vscode.ChatRequestTurn | vscode.ChatResponseTurn)[]): {
    sessionId?: string
    title?: string
} {
    for (let i = history.length - 1; i >= 0; i--) {
        const turn = history[i]
        if (!('result' in turn)) continue
        const meta = (turn.result?.metadata ?? {}) as any
        const sessionId = typeof meta?.[SESSION_ID_KEY] === 'string' ? meta[SESSION_ID_KEY] : undefined
        const title = typeof meta?.[SESSION_TITLE_KEY] === 'string' ? meta[SESSION_TITLE_KEY] : undefined
        if (sessionId) return { sessionId, title }
    }
    return {}
}

function responsePartsToText(
    parts: readonly (
        | vscode.ChatResponseMarkdownPart
        | vscode.ChatResponseFileTreePart
        | vscode.ChatResponseAnchorPart
        | vscode.ChatResponseCommandButtonPart
    )[]
): string {
    let out = ''
    for (const part of parts as readonly any[]) {
        const v = part?.value
        if (typeof v === 'string') {
            out += v
            continue
        }
        if (v && typeof v === 'object' && typeof v.value === 'string') {
            out += v.value
        }
    }
    return out
}

function buildLmMessages(
    history: readonly (vscode.ChatRequestTurn | vscode.ChatResponseTurn)[],
    prompt: string
): vscode.LanguageModelChatMessage[] {
    const messages: vscode.LanguageModelChatMessage[] = []
    for (const turn of history) {
        if ('prompt' in turn && typeof turn.prompt === 'string') {
            messages.push(vscode.LanguageModelChatMessage.User(turn.prompt))
            continue
        }
        if ('response' in turn && Array.isArray(turn.response)) {
            const text = responsePartsToText(turn.response)
            if (text.trim()) messages.push(vscode.LanguageModelChatMessage.Assistant(text))
        }
    }
    messages.push(vscode.LanguageModelChatMessage.User(prompt))
    return messages
}

async function safeCountTokens(model: vscode.LanguageModelChat, text: string, token: vscode.CancellationToken): Promise<number | undefined> {
    try {
        const count = await model.countTokens(text, token)
        if (typeof count === 'number' && Number.isFinite(count)) return count
    } catch {
        // ignore
    }
    return undefined
}

export function activate(context: vscode.ExtensionContext) {
    context.subscriptions.push(
        vscode.commands.registerCommand('codetether.pickCodebase', async () => {
            try {
                await pickCodebase(context)
            } catch (err) {
                const msg = err instanceof Error ? err.message : String(err)
                void vscode.window.showErrorMessage(`CodeTether: failed to load codebases: ${msg}`)
            }
        })
    )

    const participant = vscode.chat.createChatParticipant('codetether', async (request, chatContext, stream, token) => {
        const apiUrl = getApiUrl()
        const apiToken = getApiToken()

        const codebaseId = await resolveCodebaseId(context)
        if (!codebaseId) {
            stream.markdown('Configure a CodeTether codebase first (run `CodeTether: Pick Codebase`).')
            return { metadata: { error: 'missing_codebase' } }
        }

        const prior = extractSessionMetadata(chatContext.history)
        const isNewSession = !prior.sessionId
        const sessionId = prior.sessionId || randomUUID()
        const title =
            prior.title ||
            (request.prompt.trim() ? request.prompt.trim().slice(0, 80) : 'VS Code Chat')

        const workspaceFolder = vscode.workspace.workspaceFolders?.[0]
        const directory = workspaceFolder?.uri?.fsPath
        const now = new Date().toISOString()

        const modelId = request.model?.id || `${request.model?.vendor ?? 'unknown'}/${request.model?.family ?? 'model'}`
        const inputTokens = await safeCountTokens(request.model, request.prompt, token)

        const ingestUrl = `${apiUrl}/v1/opencode/codebases/${encodeURIComponent(codebaseId)}/sessions/${encodeURIComponent(sessionId)}/ingest`

        const userMessageId = randomUUID()
        const userMessage = {
            id: userMessageId,
            sessionID: sessionId,
            role: 'user',
            model: modelId,
            cost: null,
            tokens: inputTokens ? ({ input: inputTokens } satisfies TokenUsage) : {},
            parts: [{ type: 'text', text: request.prompt }],
            info: { role: 'user', model: modelId, content: request.prompt },
            time: { created: now },
        }

        // Best-effort: ensure the session exists before streaming the model response.
        try {
            await postJson(
                ingestUrl,
                {
                    source: 'vscode.chat',
                    worker_id: 'vscode',
                    session: {
                        title,
                        directory,
                        project_id: 'vscode',
                        version: 'vscode-chat',
                        created_at: now,
                        updated_at: now,
                        summary: {
                            source: 'vscode.chat',
                            participant: 'codetether',
                            workspace: workspaceFolder?.name,
                            model: {
                                id: request.model?.id,
                                vendor: request.model?.vendor,
                                family: request.model?.family,
                                version: request.model?.version,
                            },
                            is_new_session: isNewSession,
                        },
                    },
                    messages: [userMessage],
                },
                apiToken
            )
        } catch (err) {
            // Don't block chat if persistence is unavailable.
            const msg = err instanceof Error ? err.message : String(err)
            console.warn(`CodeTether ingest failed (user message): ${msg}`)
        }

        let assistantText = ''
        try {
            const lmMessages = buildLmMessages(chatContext.history, request.prompt)
            const lmResponse = await request.model.sendRequest(lmMessages, {}, token)
            for await (const chunk of lmResponse.text) {
                assistantText += chunk
                stream.markdown(chunk)
            }
        } catch (err) {
            const msg = err instanceof Error ? err.message : String(err)
            stream.markdown(`\n\n_Error: ${msg}_`)
        }

        if (assistantText.trim()) {
            const assistantNow = new Date().toISOString()
            const outputTokens = await safeCountTokens(request.model, assistantText, token)
            const assistantMessage = {
                id: randomUUID(),
                sessionID: sessionId,
                role: 'assistant',
                model: modelId,
                cost: null,
                tokens: outputTokens ? ({ output: outputTokens } satisfies TokenUsage) : {},
                parts: [{ type: 'text', text: assistantText }],
                info: { role: 'assistant', model: modelId, content: assistantText },
                time: { created: assistantNow },
            }

            try {
                await postJson(
                    ingestUrl,
                    {
                        source: 'vscode.chat',
                        worker_id: 'vscode',
                        session: {
                            title,
                            directory,
                            project_id: 'vscode',
                            version: 'vscode-chat',
                            created_at: now,
                            updated_at: assistantNow,
                            summary: {
                                source: 'vscode.chat',
                                participant: 'codetether',
                                workspace: workspaceFolder?.name,
                            },
                        },
                        messages: [assistantMessage],
                    },
                    apiToken
                )
            } catch (err) {
                const msg = err instanceof Error ? err.message : String(err)
                console.warn(`CodeTether ingest failed (assistant message): ${msg}`)
            }
        }

        return {
            metadata: {
                [SESSION_ID_KEY]: sessionId,
                [SESSION_TITLE_KEY]: title,
            },
        }
    })

    context.subscriptions.push(participant)
}

export function deactivate() {}

