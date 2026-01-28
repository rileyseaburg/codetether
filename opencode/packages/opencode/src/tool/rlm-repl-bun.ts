import { spawn, type ChildProcess } from "child_process"
import path from "path"
import fs from "fs/promises"
import { Global } from "../global"
import { Identifier } from "../id/id"

const LLM_REQUEST_START = "__LLM_REQUEST__"
const LLM_REQUEST_END = "__LLM_REQUEST_END__"
const EXECUTION_TIMEOUT = 30_000

/**
 * Bun/JavaScript REPL for RLM processing.
 * Native runtime - no Python/Rust dependency required.
 * Faster startup, same functionality.
 */
export namespace RlmReplBun {
  export interface Repl {
    proc: ChildProcess
    workdir: string
    contextLength: number
  }

  export interface CreateOptions {
    workdir?: string
  }

  function generateInitCode(context: string | string[]): string {
    const isArray = Array.isArray(context)
    const contextValue = JSON.stringify(context)

    return `
const readline = require('readline');
const rl = readline.createInterface({ input: process.stdin, output: process.stdout, terminal: false });

// Context variable
const context = ${isArray ? `${contextValue}.join("\\n")` : contextValue};
const contextParts = ${isArray ? contextValue : `[${contextValue}]`};

// Helper functions - llm_query for recursive sub-LM calls (per RLM paper)
function llm_query(prompt, output = "text") {
  const request = JSON.stringify({ prompt, output });
  console.log("${LLM_REQUEST_START}" + request + "${LLM_REQUEST_END}");
  // Response comes on next line - handled by execute
  return new Promise(resolve => {
    rl.once('line', line => {
      try {
        const resp = JSON.parse(line);
        resolve(resp.response || "");
      } catch {
        resolve(line.trim());
      }
    });
  });
}
// Alias for compatibility
const llmQuery = llm_query;

// Batch/parallel llm_query - runs multiple queries and returns array of results
// Usage: const results = await llm_query_batch([prompt1, prompt2, prompt3])
async function llm_query_batch(prompts, output = "text") {
  // Run sequentially for now (parallel requires protocol changes)
  // But this provides the API for future optimization
  const results = [];
  for (const prompt of prompts) {
    const result = await llm_query(prompt, output);
    results.push(result);
  }
  return results;
}
const llmQueryBatch = llm_query_batch;

function FINAL(answer) {
  console.log("__FINAL__" + String(answer) + "__FINAL_END__");
}

function FINAL_VAR(varName) {
  console.log("__FINAL_VAR__" + varName + "__FINAL_VAR_END__");
}

// Utility functions for analysis
function lines() { return context.split("\\n"); }
function head(n = 10) { return lines().slice(0, n).join("\\n"); }
function tail(n = 10) { return lines().slice(-n).join("\\n"); }
function grep(pattern) {
  const re = pattern instanceof RegExp ? pattern : new RegExp(pattern, 'gi');
  return lines().filter(l => re.test(l));
}
function count(pattern) {
  const re = pattern instanceof RegExp ? pattern : new RegExp(pattern, 'gi');
  return (context.match(re) || []).length;
}
function chunk(n = 5) {
  // Split context into n roughly equal chunks
  const allLines = lines();
  const chunkSize = Math.max(1, Math.ceil(allLines.length / n));
  const chunks = [];
  for (let i = 0; i < allLines.length; i += chunkSize) {
    chunks.push(allLines.slice(i, i + chunkSize).join("\\n"));
  }
  return chunks;
}
function slice(start, end) {
  // Slice context by character positions
  return context.slice(start, end);
}
function search(pattern, limit = 10) {
  // Search and return matching lines with context
  const re = pattern instanceof RegExp ? pattern : new RegExp(pattern, 'gi');
  const matches = [];
  const allLines = lines();
  for (let i = 0; i < allLines.length && matches.length < limit; i++) {
    if (re.test(allLines[i])) {
      matches.push({ line: i + 1, content: allLines[i] });
    }
  }
  return matches;
}

console.log(\`Context loaded: \${context.length} characters, \${lines().length} lines\`);

// Read and execute code blocks
rl.on('line', async (line) => {
  if (line.startsWith('__CODE_START_')) {
    const execId = line.match(/__CODE_START_(\\d+)__/)?.[1];
    let code = '';
    const endMarker = \`__CODE_END_\${execId}__\`;
    
    const codeHandler = (codeLine) => {
      if (codeLine === endMarker) {
        rl.off('line', codeHandler);
        try {
          // Use AsyncFunction to support await
          const AsyncFunction = Object.getPrototypeOf(async function(){}).constructor;
          const fn = new AsyncFunction('context', 'contextParts', 'llm_query', 'llmQuery', 'llm_query_batch', 'llmQueryBatch',
            'FINAL', 'FINAL_VAR', 'lines', 'head', 'tail', 'grep', 'count', 'chunk', 'slice', 'search', code);
          fn(context, contextParts, llm_query, llmQuery, llm_query_batch, llmQueryBatch,
            FINAL, FINAL_VAR, lines, head, tail, grep, count, chunk, slice, search)
            .then(() => console.log(\`__DONE_\${execId}__\`))
            .catch(e => { console.error('Error:', e.message); console.log(\`__DONE_\${execId}__\`); });
        } catch (e) {
          console.error('Parse Error:', e.message);
          console.log(\`__DONE_\${execId}__\`);
        }
      } else {
        code += codeLine + '\\n';
      }
    };
    rl.on('line', codeHandler);
  }
});
`
  }

  export async function create(context: string | string[], options?: CreateOptions): Promise<Repl> {
    const id = Identifier.ascending("tool")
    const baseDir = path.join(Global.Path.data, "rlm-repl-bun")
    await fs.mkdir(baseDir, { recursive: true })

    const workdir = options?.workdir ?? path.join(baseDir, id)
    if (!options?.workdir) {
      await fs.mkdir(workdir, { recursive: true })
    }

    // Write init script
    const initCode = generateInitCode(context)
    const scriptPath = path.join(workdir, "_rlm_init.js")
    await fs.writeFile(scriptPath, initCode)

    // Try bun first, fall back to node
    const runtime = await detectRuntime()
    const proc = spawn(runtime, [scriptPath], {
      cwd: workdir,
      stdio: ["pipe", "pipe", "pipe"],
    })

    const contextLength = Array.isArray(context) ? context.join("\n").length : context.length
    const repl: Repl = { proc, workdir, contextLength }

    // Wait for init
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

  async function detectRuntime(): Promise<string> {
    // Check for bun first
    try {
      const proc = spawn("bun", ["--version"], { stdio: "pipe" })
      await new Promise<void>((resolve, reject) => {
        proc.on("close", (code) => (code === 0 ? resolve() : reject()))
        proc.on("error", reject)
      })
      return "bun"
    } catch {
      return "node"
    }
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
        resolve({ stdout, stderr, final: finalAnswer })
      }

      const processBuffer = async () => {
        // Check for FINAL
        const finalMatch = buffer.match(/__FINAL__([\s\S]*?)__FINAL_END__/)
        if (finalMatch) {
          finalAnswer = finalMatch[1]
          buffer = buffer.replace(/__FINAL__[\s\S]*?__FINAL_END__/, "")
        }

        // Extract LLM requests
        while (true) {
          const startIdx = buffer.indexOf(LLM_REQUEST_START)
          if (startIdx === -1) break

          const endIdx = buffer.indexOf(LLM_REQUEST_END, startIdx)
          if (endIdx === -1) break

          stdout += buffer.slice(0, startIdx)

          const jsonStart = startIdx + LLM_REQUEST_START.length
          const jsonStr = buffer.slice(jsonStart, endIdx)
          buffer = buffer.slice(endIdx + LLM_REQUEST_END.length)

          try {
            const request = JSON.parse(jsonStr)
            const response = await onLlmQuery(request.prompt, request.output)
            repl.proc.stdin?.write(JSON.stringify({ response }) + "\n")
          } catch {
            repl.proc.stdin?.write(JSON.stringify({ response: "" }) + "\n")
          }
        }

        // Check for done
        const doneIdx = buffer.indexOf(doneMarker)
        if (doneIdx !== -1) {
          stdout += buffer.slice(0, doneIdx)
          buffer = buffer.slice(doneIdx + doneMarker.length)
          finish()
          return
        }

        stdout += buffer
        buffer = ""
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

      repl.proc.stdin?.write(`${startMarker}\n${code}\n${endMarker}\n`)

      timer = setTimeout(() => {
        cleanup()
        reject(new Error("Execution timed out after 30 seconds"))
      }, EXECUTION_TIMEOUT)
    })
  }

  export async function destroy(repl: Repl): Promise<void> {
    repl.proc.kill()
    await fs.rm(repl.workdir, { recursive: true, force: true }).catch(() => {})
  }

  export async function isAvailable(): Promise<boolean> {
    // Always available - falls back to node
    return true
  }
}
