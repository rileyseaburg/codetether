import { spawn, type ChildProcess } from "child_process"
import path from "path"
import fs from "fs/promises"
import { Global } from "../global"
import { Identifier } from "../id/id"

const LLM_REQUEST_START = "__LLM_REQUEST__"
const LLM_REQUEST_END = "__LLM_REQUEST_END__"
const EXECUTION_TIMEOUT = 30_000

export namespace RlmRepl {
  export interface Repl {
    proc: ChildProcess
    workdir: string
  }

  export interface CreateOptions {
    disableNetwork?: boolean
    workdir?: string
  }

  function generateInitCode(context: string | string[]): string {
    const isArray = Array.isArray(context)
    const contextValue = JSON.stringify(context)

    // This creates a persistent Python process that reads code blocks from stdin
    // and executes them using exec(), allowing for stateful execution with llm_query support
    return `
import sys
import json

def llm_query(prompt, output="json"):
    """Query the LLM with a prompt and return the response."""
    request = json.dumps({"prompt": prompt, "output": output})
    print(f"${LLM_REQUEST_START}" + request + "${LLM_REQUEST_END}", flush=True)
    response_line = sys.stdin.readline()
    try:
        response = json.loads(response_line)
        return response.get("response", "")
    except json.JSONDecodeError:
        return response_line.strip()

def llm_query_batch(prompts, output="json"):
    """Query the LLM with multiple prompts and return list of responses.
    Usage: results = llm_query_batch([prompt1, prompt2, prompt3])
    """
    results = []
    for prompt in prompts:
        result = llm_query(prompt, output)
        results.append(result)
    return results

def FINAL(answer):
    """Mark the final answer for RLM processing."""
    print(f"__FINAL__{answer}__FINAL_END__", flush=True)

def FINAL_VAR(var_name):
    """Mark a variable as the final answer."""
    print(f"__FINAL_VAR__{var_name}__FINAL_VAR_END__", flush=True)

# Utility functions for analysis (matching Bun REPL helpers)
def lines():
    """Return context split by newlines."""
    return context.split("\\n") if isinstance(context, str) else context

def head(n=10):
    """Return first n lines."""
    return "\\n".join(lines()[:n])

def tail(n=10):
    """Return last n lines."""
    return "\\n".join(lines()[-n:])

def grep(pattern):
    """Filter lines matching pattern (regex or string)."""
    import re
    if isinstance(pattern, str):
        pattern = re.compile(pattern, re.IGNORECASE)
    return [l for l in lines() if pattern.search(l)]

def count(pattern):
    """Count matches of pattern in context."""
    import re
    if isinstance(pattern, str):
        pattern = re.compile(pattern, re.IGNORECASE)
    return len(pattern.findall(context if isinstance(context, str) else "\\n".join(context)))

def chunk(n=5):
    """Split context into n roughly equal chunks."""
    all_lines = lines()
    chunk_size = max(1, len(all_lines) // n)
    return ["\\n".join(all_lines[i:i+chunk_size]) for i in range(0, len(all_lines), chunk_size)]

context = ${contextValue}
${isArray ? `context_joined = "\\n".join(context)` : ""}

_char_count = len(${isArray ? "context_joined" : "context"})
_line_count = ${isArray ? "len(context)" : "context.count('\\n') + 1"}
print(f"Context loaded: {_char_count} characters, {_line_count} lines", flush=True)
del _char_count, _line_count

# Global namespace for exec
_globals = {
    'llm_query': llm_query,
    'llm_query_batch': llm_query_batch,
    'FINAL': FINAL,
    'FINAL_VAR': FINAL_VAR,
    'context': context,
    ${isArray ? "'context_joined': context_joined," : ""}
    'lines': lines,
    'head': head,
    'tail': tail,
    'grep': grep,
    'count': count,
    'chunk': chunk,
    'json': json,
    'sys': sys,
    're': __import__('re'),
}

# Read and execute code blocks
while True:
    marker_line = sys.stdin.readline()
    if not marker_line:
        break
    marker_line = marker_line.strip()
    if not marker_line.startswith("__CODE_START_"):
        continue
    
    code_lines = []
    end_marker = marker_line.replace("_START_", "_END_")
    while True:
        line = sys.stdin.readline()
        if not line or line.strip() == end_marker:
            break
        code_lines.append(line)
    
    code = "".join(code_lines)
    try:
        exec(code, _globals)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr, flush=True)
    
    done_marker = marker_line.replace("__CODE_START_", "__DONE_")
    print(done_marker, flush=True)
`
  }

  export async function create(context: string | string[], options?: CreateOptions): Promise<Repl> {
    const id = Identifier.ascending("tool")
    const baseDir = path.join(Global.Path.data, "rlm-repl")
    await fs.mkdir(baseDir, { recursive: true })

    const workdir = options?.workdir ?? path.join(baseDir, id)
    if (!options?.workdir) {
      await fs.mkdir(workdir, { recursive: true })
    }

    const disableNetwork = options?.disableNetwork !== false

    const env: Record<string, string> = { ...process.env } as Record<string, string>
    if (disableNetwork) {
      env.NO_PROXY = "*"
      env.no_proxy = "*"
    }

    // Write init script to file and run it
    const initCode = generateInitCode(context)
    const scriptPath = path.join(workdir, "_rlm_init.py")
    await fs.writeFile(scriptPath, initCode)

    const proc = spawn("python3", ["-u", scriptPath], {
      cwd: workdir,
      env,
      stdio: ["pipe", "pipe", "pipe"],
    })

    const repl: Repl = { proc, workdir }

    // Wait for init to complete (it prints "Context loaded: ...")
    await new Promise<void>((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error("Init timed out")), 10000)
      const onData = (chunk: Buffer) => {
        if (chunk.toString().includes("Context loaded:")) {
          clearTimeout(timeout)
          proc.stdout?.off("data", onData)
          resolve()
        }
      }
      proc.stdout?.on("data", onData)
      proc.on("error", reject)
    })

    return repl
  }

  export async function execute(
    repl: Repl,
    code: string,
    onLlmQuery: (prompt: string, output?: string) => Promise<string>,
  ): Promise<{ stdout: string; stderr: string }> {
    return new Promise((resolve, reject) => {
      let stdout = ""
      let stderr = ""
      let buffer = ""
      let timer: ReturnType<typeof setTimeout> | undefined
      let finished = false

      const execId = Date.now()
      const startMarker = `__CODE_START_${execId}__`
      const endMarker = `__CODE_END_${execId}__`
      const doneMarker = `__DONE_${execId}__`

      const cleanup = () => {
        if (timer) clearTimeout(timer)
        repl.proc.stdout?.off("data", onStdout)
        repl.proc.stderr?.off("data", onStderr)
      }

      const finish = () => {
        if (finished) return
        finished = true
        cleanup()
        resolve({ stdout, stderr })
      }

      const processBuffer = async () => {
        // Extract complete LLM requests from buffer
        while (true) {
          const startIdx = buffer.indexOf(LLM_REQUEST_START)
          if (startIdx === -1) {
            // Check for done marker
            const doneIdx = buffer.indexOf(doneMarker)
            if (doneIdx !== -1) {
              stdout += buffer.slice(0, doneIdx)
              buffer = buffer.slice(doneIdx + doneMarker.length)
              finish()
              return
            }
            stdout += buffer
            buffer = ""
            break
          }

          const endIdx = buffer.indexOf(LLM_REQUEST_END, startIdx)
          if (endIdx === -1) break

          // Add text before the marker to stdout
          stdout += buffer.slice(0, startIdx)

          // Parse the request
          const jsonStart = startIdx + LLM_REQUEST_START.length
          const jsonStr = buffer.slice(jsonStart, endIdx)
          buffer = buffer.slice(endIdx + LLM_REQUEST_END.length)

          try {
            const request = JSON.parse(jsonStr)
            const response = await onLlmQuery(request.prompt, request.output)
            const responseJson = JSON.stringify({ response }) + "\n"
            repl.proc.stdin?.write(responseJson)
          } catch {
            repl.proc.stdin?.write(JSON.stringify({ response: "" }) + "\n")
          }
        }
      }

      const onStdout = (chunk: Buffer) => {
        buffer += chunk.toString()
        processBuffer()
      }

      const onStderr = (chunk: Buffer) => {
        stderr += chunk.toString()
      }

      repl.proc.stdout?.on("data", onStdout)
      repl.proc.stderr?.on("data", onStderr)

      // Send code block with markers
      repl.proc.stdin?.write(`${startMarker}\n${code}\n${endMarker}\n`)

      timer = setTimeout(() => {
        cleanup()
        reject(new Error("Execution timed out after 30 seconds"))
      }, EXECUTION_TIMEOUT)
    })
  }

  export async function getVariable(repl: Repl, name: string): Promise<string> {
    const code = `print(repr(${name}), flush=True)`
    const result = await execute(repl, code, async () => "")
    return result.stdout.trim()
  }

  export async function destroy(repl: Repl): Promise<void> {
    repl.proc.kill()
    await fs.rm(repl.workdir, { recursive: true, force: true }).catch(() => {})
  }
}
