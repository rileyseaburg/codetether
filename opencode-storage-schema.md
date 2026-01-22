# OpenCode Storage Schema

## Directory Structure

The OpenCode storage directory contains the following subdirectories:
- `message/` - Message data organized by session ID
- `part/` - Part data (nested under message directories)
- `project/` - Project configuration
- `session/` - Session metadata
- `session_diff/` - Session diff data
- `todo/` - Todo/task data
- `migration/` - Migration data (if present)

---

## 1. Project Schema

File: {project_id}.json or global.json

Location: /home/riley/.local/share/opencode/storage/project/

Schema:
  {
    id: string,              // Unique project identifier (UUID format)
    worktree: string,         // Working directory path
    vcs: string?,            // Version control system (e.g., git) - optional
    time: {
      created: number,       // Creation timestamp (milliseconds since epoch)
      updated: number        // Last update timestamp (milliseconds since epoch)
    },
    sandboxes: array          // List of sandbox configurations (currently empty array)
  }

Fields:
- id (required): Unique project ID
- worktree (required): Path to working directory
- vcs (optional): Version control system identifier
- time.created (required): Unix timestamp of creation
- time.updated (required): Unix timestamp of last update
- sandboxes (required): Array of sandbox configurations
 
---

## 2. Session Schema

File: {session_id}.json

Location: /home/riley/.local/share/opencode/storage/session/

Schema:
  {
    id: string,              // Unique session identifier (UUID format)
    version: string,           // Version string (e.g., 0.0.0-dev-202601110150)
    projectID: string,         // Reference to associated project ID
    directory: string,         // Working directory path
    title: string,             // Session title/description
    time: {
      created: number,       // Creation timestamp
      updated: number        // Last update timestamp
    },
    summary: {
      additions: number,       // Total additions in session
      deletions: number,       // Total deletions in session
      files: number            // Total number of files affected
    }
  }

Fields:
- id (required): Unique session ID starting with ses_
- version (required): Software version string
- projectID (required): Associated project ID
- directory (required): Working directory
- title (required): Session title
- time.created (required): Creation timestamp
- time.updated (required): Update timestamp
- summary.additions (optional): Number of additions
- summary.deletions (optional): Number of deletions
- summary.files (optional): Number of files affected

---

## 3. Message Schema

File: {session_id}/{message_id}.json

Location: /home/riley/.local/share/opencode/storage/message/

Schema:
  {
    id: string,              // Unique message identifier (UUID format)
    sessionID: string,         // Reference to parent session
    role: string,              // Message role: user or assistant
    time: {
      created: number,       // Creation timestamp (milliseconds)
      completed: number?     // Completion timestamp (assistant messages only)
    },
    summary: {
      title: string?,         // Optional summary title
      diffs: array?           // Array of change diffs
    },
    parentID: string?,         // Parent message ID (for threading)
    modelID: string?,          // Model identifier used (assistant messages)
    providerID: string?,        // Provider ID (e.g., zai-coding-plan)
    mode: string?,             // Mode: build, chat, etc.
    path: {
      cwd: string,            // Current working directory
      root: string,           // Project root directory
    },
    cost: number?,             // Cost of request
    tokens: {
      input: number,          // Input tokens
      output: number,         // Output tokens
      reasoning: number,       // Reasoning tokens
      cache: {
        read: number,         // Cache read tokens
        write: number         // Cache write tokens
      }
    },
    agent: string?,             // Agent identifier (e.g., build)
    model: {
      providerID: string,     // Model provider ID
      modelID: string         // Model ID (e.g., claude-opus-4-5)
    }
  }

Fields:
- id (required): Unique message ID prefixed with msg_
- sessionID (required): Parent session ID
- role (required): user or assistant
- time.created (required): Creation timestamp
- time.completed (optional): Completion timestamp for assistant messages
- summary.title (optional): Summary title
- summary.diffs (optional): Array of Diff objects
- parentID (optional): Parent message for threading
- modelID (optional): Model used for generation
- providerID (optional): Provider of model
- mode (optional): Session mode
- path.cwd (optional): Current working directory
- path.root (optional): Project root
- cost (optional): Monetary cost
- tokens.input (optional): Number of input tokens
- tokens.output (optional): Number of output tokens
- tokens.reasoning (optional): Number of reasoning tokens
- tokens.cache.read (optional): Cache read
- tokens.cache.write (optional): Cache write
- agent (optional): Agent type
- model.providerID (optional): Alternative provider field
- model.modelID (optional): Alternative model field

---

## 4. Part Schema

File: part/msg_{message_id}/prt_{part_id}.json

Location: /home/riley/.local/share/opencode/storage/part/

Schema:
  {
    id: string,              // Unique part identifier (UUID format)
    sessionID: string,         // Reference to parent session
    messageID: string,         // Reference to parent message
    type: string,              // Part type: text or potentially other types
    text: string,              // Text content for text parts
    time: {
      start: number,          // Start timestamp (milliseconds)
      end: number              // End timestamp (milliseconds)
    }
  }

Fields:
- id (required): Unique part ID prefixed with prt_
- sessionID (required): Parent session ID
- messageID (required): Parent message ID
- type (required): Content type
- text (required): Text content
- time.start (optional): Start timestamp
- time.end (optional): End timestamp

---

## 5. Session Diff Schema

File: session_diff/{session_id}.json

Location: /home/riley/.local/share/opencode/storage/session_diff/

Schema:
  [
    {
      file: string,           // File path that was changed
      before: string,         // Original content
      after: string,            // Modified content
      additions: number,       // Number of lines added
      deletions: number         // Number of lines deleted
    }
  ]

Fields:
- Array of Diff objects
- Each object represents a file change
- file (required): File path relative to project
- before (required): Original file content
- after (required): New file content
- additions (required): Positive change count
- deletions (required): Negative change count

---

## 6. Todo Schema

File: todo/{session_id}.json

Location: /home/riley/.local/share/opencode/storage/todo/

Schema:
  [
    {
      id: string,              // Todo item ID
      content: string,         // Todo description
      status: string,           // Status: completed, pending, in_progress, etc.
      priority: string         // Priority: high, medium, low
    }
  ]

Fields:
- Array of Todo objects
- id (required): Todo item identifier
- content (required): Todo description
- status (required): Current status of the todo
- priority (required): Priority level

---

## ID Formats

The system uses specific ID formats:

- Project IDs: {random_hex_string}, e.g., 2cd4e892d12c4ab6d769926a0ffa76d89f2777fe
- Session IDs: ses_{random_hex_string}, e.g., ses_470a4a3c9ffeyELffpIzEVZF64
- Message IDs: msg_{random_hex_string}, e.g., msg_bd6ca3a6b001k84oMT2O4UJuqm
- Part IDs: prt_{random_hex_string}, e.g., prt_bd6ca3d6d00167pli0PH3AD4wu
- Todo IDs: Sequential numbers as strings, e.g., 1, 2, 3

---

## Timestamp Format

All timestamps are stored as Unix milliseconds since epoch (number, not string).

---

## Data Relationships

  project (1) ---- (projectID) ----> (many) session (1) ---- (sessionID) ----> (many) message
         |                         |                                              |
         |                         |                                              +-- (messageID) --> (many) part
         |                         |
         +-- (id) ------------>-- (many) ---- (id) ---> session_diff

- A project has many sessions
- A session has many messages
- A message can have many parts
- A session has one session_diff (array of file changes)

---

## Notes

1. Special project ID global represents a root/global project
2. The message directory stores message files in subdirectories named by session ID
3. The part directory has a flat structure with msg_ID in the filename to group parts by message
4. Session diffs can be very large (files with full content)
5. Some JSON files in session_diff may be as small as 2 bytes (possibly empty or minimal diffs)
6. The migration directory was listed but does not appear to contain JSON files in the current setup

---

## Example File Paths

- Project: project/global.json
- Session: session/ses_470a4a3c9ffeyELffpIzEVZF64.json
- Message: message/ses_470a4a3c9ffeyELffpIzEVZF64/msg_b8f5b5caf9e001MJOd48QrUpKfar.json
- Part: part/msg_bd6ca3a6b001k84oMT2O4UJuqm/prt_bd6ca3d6d00167pli0PH3AD4wu.json
- Session Diff: session_diff/ses_470a4a3c9ffeyELffpIzEVZF64.json
- Todo: todo/ses_470a4a3c9ffeyELffpIzEVZF64.json
