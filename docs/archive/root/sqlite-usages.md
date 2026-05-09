# SQLite Usages in A2A Server

This document catalogs all SQLite usages in the codebase. The goal is to eliminate SQLite dependencies and migrate to PostgreSQL for all durable storage.

## Critical Issues

### 1. `a2a_server/monitor_api.py` - PostgreSQL Messages Implemented (SQLite Fallback Remaining)

**Location:** `/home/riley/A2A-Server-MCP/a2a_server/monitor_api.py`

**Description:** Main message storage now uses PostgreSQL. SQLite fallback still present but unused.

**PostgreSQL Implementation:**
- `database.py` now includes `db_save_monitor_message()`, `db_list_monitor_messages()`, `db_get_monitor_stats()`, and `db_count_monitor_messages()`
- Messages stored in `monitor_messages` table with full metadata, response times, and token counts

**Status:** ✅ PARTIALLY IMPLEMENTED - PostgreSQL storage functions exist in `database.py`. `monitor_api.py` still has SQLite code but falls back to in-memory storage (line 115 in monitor_api.py shows this).

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

### 4. `a2a_server/task_manager.py` - PostgreSQL Persistence Implemented

**Location:** `/home/riley/A2A-Server-MCP/a2a_server/task_manager.py`

**Description:** PersistentTaskManager now uses PostgreSQL for task storage.

**Status:** ✅ IMPLEMENTED - The `PersistentTaskManager` class uses asyncpg to store tasks in the `a2a_tasks` table.

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

**Status:** ✅ PARTIALLY COMPLETE - PostgreSQL functions exist in `database.py`

1. Add message storage functions to `database.py`:
   - `db_save_monitor_message()` ✅
   - `db_list_monitor_messages()` ✅
   - `db_get_monitor_stats()` ✅
   - `db_count_monitor_messages()` ✅

2. Update `monitor_api.py`:
   - Import database functions ✅ (partially)
   - Replace SQLite operations with PostgreSQL calls (remaining)
   - Remove `_use_sqlite` and `_init_sqlite()` methods (remaining)
   - Remove `sqlite3` import (remaining)

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
