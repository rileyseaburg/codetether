import { spawn, type ChildProcess } from "child_process"
import path from "path"
import fs from "fs/promises"
import { Global } from "../global"
import { Identifier } from "../id/id"

const LLM_REQUEST_START = "__LLM_REQUEST__"
const LLM_REQUEST_END = "__LLM_REQUEST_END__"
const EXECUTION_TIMEOUT = 60_000 // Longer timeout for Rust compilation
const INIT_TIMEOUT = 30_000 // First compilation takes longer

export namespace RlmReplRust {
  export interface Repl {
    proc: ChildProcess
    workdir: string
    ready: boolean
  }

  export interface CreateOptions {
    workdir?: string
    preloadCrates?: string[]
  }

  /**
   * Generate the initial Rust code that sets up the REPL environment.
   * evcxr allows us to define variables and functions that persist across evaluations.
   */
  function generateInitCode(context: string | string[]): string {
    const isArray = Array.isArray(context)
    // Escape the context for Rust string literal
    const escaped = JSON.stringify(isArray ? context : [context])

    // For arrays, we join them; for strings, we use directly
    return `
// Load context
let context_parts: Vec<&str> = serde_json::from_str(r#"${escaped}"#).unwrap_or_default();
let context: &str = if context_parts.len() == 1 {
    Box::leak(context_parts[0].to_string().into_boxed_str())
} else {
    Box::leak(context_parts.join("\\n").into_boxed_str())
};
${isArray ? `let context_joined: &str = context;` : ""}

let char_count = context.len();
let line_count = context.lines().count();
println!("Context loaded: {} characters, {} lines", char_count, line_count);
`
  }

  /**
   * Generate the prelude code that adds helper functions and macros.
   */
  function generatePrelude(): string {
    return `
// Helper macro for final answers
macro_rules! FINAL {
    ($answer:expr) => {{
        println!("__FINAL_ANSWER__{}__FINAL_ANSWER_END__", $answer);
    }};
}

macro_rules! FINAL_VAR {
    ($var:ident) => {{
        println!("__FINAL_VAR__{}__FINAL_VAR_END__", stringify!($var));
    }};
}

// Helper function for LLM queries (sends request, receives response via stdio)
fn llm_query(prompt: &str) -> String {
    println!("${LLM_REQUEST_START}{{\\\"prompt\\\":{}}}\${LLM_REQUEST_END}", serde_json::to_string(prompt).unwrap_or_default());
    let mut response = String::new();
    std::io::stdin().read_line(&mut response).ok();
    if let Ok(v) = serde_json::from_str::<serde_json::Value>(&response) {
        v.get("response").and_then(|r| r.as_str()).unwrap_or("").to_string()
    } else {
        response.trim().to_string()
    }
}
`
  }

  export async function create(context: string | string[], options?: CreateOptions): Promise<Repl> {
    const id = Identifier.ascending("tool")
    const baseDir = path.join(Global.Path.data, "rlm-repl-rust")
    await fs.mkdir(baseDir, { recursive: true })

    const workdir = options?.workdir ?? path.join(baseDir, id)
    if (!options?.workdir) {
      await fs.mkdir(workdir, { recursive: true })
    }

    const env: Record<string, string> = { ...process.env } as Record<string, string>

    // Spawn evcxr process
    const proc = spawn("evcxr", ["--disable-readline"], {
      cwd: workdir,
      env,
      stdio: ["pipe", "pipe", "pipe"],
    })

    const repl: Repl = { proc, workdir, ready: false }

    // Wait for evcxr to be ready (it prints a welcome message or prompt)
    await new Promise<void>((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error("evcxr init timed out")), INIT_TIMEOUT)
      let buffer = ""

      const onData = (chunk: Buffer) => {
        buffer += chunk.toString()
        // evcxr is ready when it shows its prompt or finishes initial output
        if (buffer.includes(">>") || buffer.includes("Welcome")) {
          clearTimeout(timeout)
          proc.stdout?.off("data", onData)
          resolve()
        }
      }

      const onError = (err: Error) => {
        clearTimeout(timeout)
        reject(new Error(`evcxr failed to start: ${err.message}. Is evcxr installed? (cargo install evcxr_repl)`))
      }

      proc.stdout?.on("data", onData)
      proc.on("error", onError)

      // If no welcome message, assume ready after brief delay
      setTimeout(() => {
        clearTimeout(timeout)
        proc.stdout?.off("data", onData)
        resolve()
      }, 2000)
    })

    // Add serde_json dependency for JSON handling
    const preloadCrates = options?.preloadCrates ?? ["serde_json", "regex"]
    for (const crate of preloadCrates) {
      await executeRaw(repl, `:dep ${crate}`)
    }

    // Load prelude with helper functions
    await executeRaw(repl, generatePrelude())

    // Load context
    const initResult = await executeRaw(repl, generateInitCode(context))
    if (!initResult.stdout.includes("Context loaded:")) {
      throw new Error(`Failed to initialize context: ${initResult.stderr || initResult.stdout}`)
    }

    repl.ready = true
    return repl
  }

  /**
   * Execute raw Rust code without processing FINAL/llm_query markers.
   */
  async function executeRaw(repl: Repl, code: string): Promise<{ stdout: string; stderr: string }> {
    return new Promise((resolve, reject) => {
      let stdout = ""
      let stderr = ""
      let timer: ReturnType<typeof setTimeout> | undefined

      const cleanup = () => {
        if (timer) clearTimeout(timer)
        repl.proc.stdout?.off("data", onStdout)
        repl.proc.stderr?.off("data", onStderr)
      }

      const onStdout = (chunk: Buffer) => {
        stdout += chunk.toString()
        // evcxr shows >> prompt when ready for more input
        if (stdout.includes(">>") && !stdout.endsWith(">>")) {
          cleanup()
          // Remove the prompt from output
          stdout = stdout.replace(/^>>\s*/gm, "").replace(/\s*>>\s*$/g, "")
          resolve({ stdout: stdout.trim(), stderr: stderr.trim() })
        }
      }

      const onStderr = (chunk: Buffer) => {
        stderr += chunk.toString()
      }

      repl.proc.stdout?.on("data", onStdout)
      repl.proc.stderr?.on("data", onStderr)

      // Send code, ensuring newline
      repl.proc.stdin?.write(code.endsWith("\n") ? code : code + "\n")

      timer = setTimeout(() => {
        cleanup()
        // For commands that don't produce output, assume success
        resolve({ stdout: stdout.trim(), stderr: stderr.trim() })
      }, EXECUTION_TIMEOUT)
    })
  }

  export async function execute(
    repl: Repl,
    code: string,
    onLlmQuery: (prompt: string, output?: string) => Promise<string>,
  ): Promise<{ stdout: string; stderr: string; final?: string }> {
    return new Promise((resolve, reject) => {
      let stdout = ""
      let stderr = ""
      let buffer = ""
      let timer: ReturnType<typeof setTimeout> | undefined
      let finished = false
      let finalAnswer: string | undefined

      const execId = Date.now()
      const doneMarker = `__EXEC_DONE_${execId}__`

      const cleanup = () => {
        if (timer) clearTimeout(timer)
        repl.proc.stdout?.off("data", onStdout)
        repl.proc.stderr?.off("data", onStderr)
      }

      const finish = () => {
        if (finished) return
        finished = true
        cleanup()
        resolve({ stdout, stderr, final: finalAnswer })
      }

      const processBuffer = async () => {
        // Check for FINAL answer
        const finalMatch = buffer.match(/__FINAL_ANSWER__([\s\S]*?)__FINAL_ANSWER_END__/)
        if (finalMatch) {
          finalAnswer = finalMatch[1]
          buffer = buffer.replace(/__FINAL_ANSWER__[\s\S]*?__FINAL_ANSWER_END__/, "")
        }

        // Check for FINAL_VAR
        const finalVarMatch = buffer.match(/__FINAL_VAR__(\w+)__FINAL_VAR_END__/)
        if (finalVarMatch) {
          // Need to get the variable value
          const varName = finalVarMatch[1]
          buffer = buffer.replace(/__FINAL_VAR__\w+__FINAL_VAR_END__/, "")
          // We'll resolve the variable after the main execution
        }

        // Extract LLM requests
        while (true) {
          const startIdx = buffer.indexOf(LLM_REQUEST_START)
          if (startIdx === -1) break

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

        // Check for done marker
        const doneIdx = buffer.indexOf(doneMarker)
        if (doneIdx !== -1) {
          stdout += buffer.slice(0, doneIdx)
          buffer = buffer.slice(doneIdx + doneMarker.length)
          finish()
          return
        }

        // Check for evcxr prompt (indicates code finished executing)
        if (buffer.includes(">>") && !buffer.endsWith(">>")) {
          stdout += buffer.replace(/^>>\s*/gm, "").replace(/\s*>>\s*$/g, "")
          buffer = ""
          finish()
          return
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

      // Wrap code to print done marker when finished
      const wrappedCode = `{
${code}
println!("${doneMarker}");
}`

      repl.proc.stdin?.write(wrappedCode + "\n")

      timer = setTimeout(() => {
        cleanup()
        reject(new Error("Execution timed out after 60 seconds"))
      }, EXECUTION_TIMEOUT)
    })
  }

  export async function getVariable(repl: Repl, name: string): Promise<string> {
    const code = `println!("{:?}", ${name});`
    const result = await execute(repl, code, async () => "")
    return result.stdout.trim()
  }

  export async function destroy(repl: Repl): Promise<void> {
    repl.proc.stdin?.write(":quit\n")
    repl.proc.kill()
    await fs.rm(repl.workdir, { recursive: true, force: true }).catch(() => {})
  }

  /**
   * Check if evcxr is available on the system.
   */
  export async function isAvailable(): Promise<boolean> {
    return new Promise((resolve) => {
      const proc = spawn("evcxr", ["--version"], { stdio: ["pipe", "pipe", "pipe"] })
      proc.on("error", () => resolve(false))
      proc.on("close", (code) => resolve(code === 0))
    })
  }
}
