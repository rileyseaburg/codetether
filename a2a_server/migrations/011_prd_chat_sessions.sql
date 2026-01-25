-- PRD Chat Sessions - links PRD builder chats to OpenCode sessions
-- This allows resuming PRD conversations by loading the associated session messages

CREATE TABLE IF NOT EXISTS prd_chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    codebase_id VARCHAR(255) NOT NULL,
    session_id VARCHAR(255) NOT NULL,  -- OpenCode session ID (ses_xxx)
    title VARCHAR(500),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(codebase_id, session_id)
);

CREATE INDEX idx_prd_chat_sessions_codebase ON prd_chat_sessions(codebase_id);
CREATE INDEX idx_prd_chat_sessions_updated ON prd_chat_sessions(updated_at DESC);
