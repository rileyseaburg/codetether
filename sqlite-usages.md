# SQLite Usages in A2A Server

This document catalogs all SQLite usages in the codebase. The goal is to eliminate SQLite dependencies and migrate to PostgreSQL for all durable storage.

## Critical Issues

### 1. `a2a_server/monitor_api.py` - Primary SQLite Usage

**Location:** `/home/riley/A2A-Server-MCP/a2a_server/monitor_api.py`

**Description:** Main message storage using SQLite as fallback when PostgreSQL is unavailable.

**SQLite Path:** `data/monitor.db`

**Usages:**
- Line 16: `import sqlite3`
- Line 47: Database path configuration
- Lines 82-167: `_init_sqlite()` method for initialization
- Lines 272-283: `_get_connection()` creates SQLite connections
- Lines 387-388: Message storage to SQLite
- Lines 521, 582, 622, 640, 661, 683: Conditional checks for `_use_sqlite`

**Problem:** Messages and monitoring data fallback to SQLite instead of PostgreSQL.

**Fix Required:**
- Migrate `monitor_api.py` to use PostgreSQL via `a2a_server/database.py`
- Remove `_use_sqlite` fallback logic
- Ensure all monitor data persists to PostgreSQL

---

### 2. `a2a_server/integrated_agents_server.py` - Agent Session Storage

**Location:** `/home/riley/A2A-Server-MCP/a2a_server/integrated_agents_server.py`

**Description:** Uses `agents.memory.SQLiteSession` for conversation session caching.

**Usages:**
- Line 12: `from agents.memory import SQLiteSession`
- Line 170: `self.session_cache: Dict[str, SQLiteSession] = {}`
- Lines 174-177: `_get_session()` method creates SQLite sessions

**Problem:** Agent conversation sessions stored in SQLite instead of PostgreSQL.

**Fix Required:**
- Create PostgreSQL-backed session storage in `database.py`
- Replace `SQLiteSession` with PostgreSQL-based implementation
- Add session table to `database.py` if not exists

---

### 3. `a2a_server/agents_server.py` - Agent Session Storage

**Location:** `/home/riley/A2A-Server-MCP/a2a_server/agents_server.py`

**Description:** Uses `agents.memory.SQLiteSession` for agent sessions.

**Usages:**
- Line 15: `from agents.memory import SQLiteSession`
- Lines 188, 223: Session creation with `SQLiteSession`

**Problem:** Same as above - agent sessions in SQLite.

**Fix Required:**
- Replace with PostgreSQL-backed session storage
- Reuse session implementation from `integrated_agents_server.py` or `database.py`

---

### 4. `a2a_server/task_manager.py` - TODO Comment

**Location:** `/home/riley/A2A-Server-MCP/a2a_server/task_manager.py`

**Description:** TODO comment indicating SQLite was planned but not implemented.

**Usages:**
- Line 174: `# TODO: Implement persistent storage using SQLite or similar`

**Status:** Not yet implemented - no action needed.

**Recommendation:** When implementing, use PostgreSQL directly.

---

### 5. Documentation References

**Location:** `/home/riley/A2A-Server-MCP/a2a_server/monitor_api.py`

**Description:** Documentation mentions SQLite as the default.

**Usages:**
- Line 8: `- SQLite for persistent storage (default if writable)`

**Fix Required:** Update documentation to reflect PostgreSQL-first approach.

---

## Migration Plan

### Phase 1: Monitor API PostgreSQL Migration

1. Add message storage functions to `database.py`:
   - `db_save_message()`
   - `db_get_messages()`
   - `db_list_conversations()`

2. Update `monitor_api.py`:
   - Import database functions
   - Replace SQLite operations with PostgreSQL calls
   - Remove `_use_sqlite` and `_init_sqlite()` methods
   - Remove `sqlite3` import

3. Update documentation in `monitor_api.py`:
   - Change "SQLite for persistent storage" to "PostgreSQL for persistent storage"

### Phase 2: Agent Session PostgreSQL Migration

1. Add session storage functions to `database.py`:
   - `db_save_agent_session()`
   - `db_get_agent_session()`
   - `db_list_agent_sessions()`

2. Create new `AgentSessionStore` class in `database.py` to replace `SQLiteSession`

3. Update `integrated_agents_server.py`:
   - Replace `SQLiteSession` imports with `AgentSessionStore`
   - Update `_get_session()` to use PostgreSQL

4. Update `agents_server.py`:
   - Replace `SQLiteSession` with PostgreSQL-based store

### Phase 3: Cleanup

1. Remove `data/monitor.db` from git tracking
2. Add `data/` to `.gitignore`
3. Update deployment documentation
4. Remove SQLite-related code paths

---

## Testing

After migration, verify:

1. Server starts without SQLite initialization message
2. Messages persist across server restarts
3. Agent sessions persist across server restarts
4. All tests pass with PostgreSQL only
5. Multi-replica deployments share state correctly

---

## Related Files

- `/home/riley/A2A-Server-MCP/a2a_server/database.py` - PostgreSQL persistence layer
- `/home/riley/A2A-Server-MCP/a2a_server/monitor_api.py` - Monitor API with SQLite fallback
- `/home/riley/A2A-Server-MCP/a2a_server/integrated_agents_server.py` - Agent server with SQLite sessions
- `/home/riley/A2A-Server-MCP/a2a_server/agents_server.py` - Agents server with SQLite sessions
- `/home/riley/A2A-Server-MCP/a2a_server/task_manager.py` - Task manager (no SQLite yet)

---

## Configuration

Set PostgreSQL via environment:

```bash
export DATABASE_URL=postgresql://user:password@host:port/database
# or
export A2A_DATABASE_URL=postgresql://user:password@host:port/database
```

Without PostgreSQL configured, the system will fail to start (desired behavior after migration).
