export const JSONSchema = {
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "OpenCode Storage Schema",
  "description": "JSON Schema definitions for OpenCode storage data types",
  "definitions": {
    "Project": {
      "type": "object",
      "required": ["id", "worktree", "time", "sandboxes"],
      "properties": {
        "id": {
          "type": "string",
          "description": "Unique project identifier (UUID format)"
        },
        "worktree": {
          "type": "string",
          "description": "Working directory path"
        },
        "vcs": {
          "type": "string",
          "description": "Version control system (e.g., git)"
        },
        "time": {
          "$ref": "#/definitions/TimeRange"
        },
        "sandboxes": {
          "type": "array",
          "items": {},
          "description": "List of sandbox configurations"
        }
      }
    },
    "Session": {
      "type": "object",
      "required": ["id", "version", "projectID", "directory", "title", "time"],
      "properties": {
        "id": {
          "type": "string",
          "pattern": "^ses_",
          "description": "Unique session identifier with ses_ prefix"
        },
        "version": {
          "type": "string",
          "description": "Software version string"
        },
        "projectID": {
          "type": "string",
          "description": "Reference to associated project ID"
        },
        "directory": {
          "type": "string",
          "description": "Working directory path"
        },
        "title": {
          "type": "string",
          "description": "Session title/description"
        },
        "time": {
          "$ref": "#/definitions/TimeRange"
        },
        "summary": {
          "$ref": "#/definitions/SessionSummary"
        }
      }
    },
    "Message": {
      "type": "object",
      "required": ["id", "sessionID", "role", "time"],
      "properties": {
        "id": {
          "type": "string",
          "pattern": "^msg_",
          "description": "Unique message identifier with msg_ prefix"
        },
        "sessionID": {
          "type": "string",
          "description": "Reference to parent session"
        },
        "role": {
          "type": "string",
          "enum": ["user", "assistant"]
        },
        "time": {
          "$ref": "#/definitions/MessageTime"
        },
        "summary": {
          "$ref": "#/definitions/MessageSummary"
        },
        "parentID": {
          "type": "string",
          "description": "Parent message ID for threading"
        },
        "modelID": {
          "type": "string",
          "description": "Model identifier used"
        },
        "providerID": {
          "type": "string",
          "description": "Provider ID"
        },
        "mode": {
          "type": "string",
          "description": "Session mode"
        },
        "path": {
          "$ref": "#/definitions/MessagePath"
        },
        "cost": {
          "type": "number"
        },
        "tokens": {
          "$ref": "#/definitions/MessageTokens"
        },
        "agent": {
          "type": "string"
        },
        "model": {
          "$ref": "#/definitions/MessageModel"
        }
      }
    },
    "Part": {
      "type": "object",
      "required": ["id", "sessionID", "messageID", "type", "text"],
      "properties": {
        "id": {
          "type": "string",
          "pattern": "^prt_",
          "description": "Unique part identifier with prt_ prefix"
        },
        "sessionID": {
          "type": "string"
        },
        "messageID": {
          "type": "string"
        },
        "type": {
          "type": "string",
          "description": "Part type: text or other types"
        },
        "text": {
          "type": "string"
        },
        "time": {
          "$ref": "#/definitions/PartTime"
        }
      }
    },
    "Diff": {
      "type": "object",
      "required": ["file", "before", "after", "additions", "deletions"],
      "properties": {
        "file": {
          "type": "string",
          "description": "File path that was changed"
        },
        "before": {
          "type": "string",
          "description": "Original content"
        },
        "after": {
          "type": "string",
          "description": "Modified content"
        },
        "additions": {
          "type": "number",
          "description": "Number of lines added"
        },
        "deletions": {
          "type": "number",
          "description": "Number of lines deleted"
        }
      }
    },
    "Todo": {
      "type": "object",
      "required": ["id", "content", "status", "priority"],
      "properties": {
        "id": {
          "type": "string",
          "description": "Todo item identifier"
        },
        "content": {
          "type": "string",
          "description": "Todo description"
        },
        "status": {
          "type": "string",
          "enum": ["pending", "in_progress", "completed", "cancelled"]
        },
        "priority": {
          "type": "string",
          "enum": ["high", "medium", "low"]
        }
      }
    },
    "TimeRange": {
      "type": "object",
      "required": ["created", "updated"],
      "properties": {
        "created": {
          "type": "number",
          "description": "Unix timestamp in milliseconds"
        },
        "updated": {
          "type": "number",
          "description": "Unix timestamp in milliseconds"
        }
      }
    },
    "MessageTime": {
      "type": "object",
      "required": ["created"],
      "properties": {
        "created": {
          "type": "number"
        },
        "completed": {
          "type": "number"
        }
      }
    },
    "PartTime": {
      "type": "object",
      "properties": {
        "start": {
          "type": "number"
        },
        "end": {
          "type": "number"
        }
      }
    },
    "SessionSummary": {
      "type": "object",
      "properties": {
        "additions": {
          "type": "number"
        },
        "deletions": {
          "type": "number"
        },
        "files": {
          "type": "number"
        }
      }
    },
    "MessageSummary": {
      "type": "object",
      "properties": {
        "title": {
          "type": "string"
        },
        "diffs": {
          "type": "array",
          "items": {
            "$ref": "#/definitions/Diff"
          }
        }
      }
    },
    "MessagePath": {
      "type": "object",
      "properties": {
        "cwd": {
          "type": "string"
        },
        "root": {
          "type": "string"
        }
      }
    },
    "TokenCache": {
      "type": "object",
      "properties": {
        "read": {
          "type": "number"
        },
        "write": {
          "type": "number"
        }
      }
    },
    "MessageTokens": {
      "type": "object",
      "properties": {
        "input": {
          "type": "number"
        },
        "output": {
          "type": "number"
        },
        "reasoning": {
          "type": "number"
        },
        "cache": {
          "$ref": "#/definitions/TokenCache"
        }
      }
    },
    "MessageModel": {
      "type": "object",
      "properties": {
        "providerID": {
          "type": "string"
        },
        "modelID": {
          "type": "string"
        }
      }
    }
  }
};

export { JSONSchema as default };