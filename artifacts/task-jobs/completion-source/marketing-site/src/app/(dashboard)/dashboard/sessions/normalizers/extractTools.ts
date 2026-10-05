import type { ToolEntry } from '../types'

export function extractTools(toolParts: any[]): ToolEntry[] {
    return toolParts
        .map((p) => ({
            tool: typeof p.tool === 'string' && p.tool ? p.tool : 'tool',
            status: typeof p.state?.status === 'string' ? p.state.status : undefined,
            title: typeof p.state?.title === 'string' ? p.state.title : undefined,
            input: p.state?.input,
            output: p.state?.output,
            error: p.state?.error,
        }))
        .filter((t) => t.tool)
}
