-- Migration: Agent Routing for Targeted Task Distribution
-- Enables send_to_agent / send_message_async with target_agent_name routing
-- 
-- Design decisions:
-- 1. target_agent_name = exact match only (no wildcards/patterns)
-- 2. Default behavior = queue indefinitely when target offline
-- 3. Optional deadline_at = fail after timeout (caller opts in)
-- 4. required_capabilities = JSONB array for capability-based routing

-- Add routing columns to task_runs
ALTER TABLE task_runs
    ADD COLUMN IF NOT EXISTS target_agent_name TEXT,
    ADD COLUMN IF NOT EXISTS required_capabilities JSONB,
    ADD COLUMN IF NOT EXISTS deadline_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS routing_failed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS routing_failure_reason TEXT;

-- Index for agent-targeted routing queries
-- Partial index on target_agent_name when set (most tasks won't have it)
CREATE INDEX IF NOT EXISTS idx_task_runs_target_agent 
    ON task_runs(target_agent_name) 
    WHERE target_agent_name IS NOT NULL;

-- Index for deadline expiration checks
CREATE INDEX IF NOT EXISTS idx_task_runs_deadline
    ON task_runs(deadline_at)
    WHERE deadline_at IS NOT NULL AND status = 'queued';

-- Update claim_next_task_run to support agent-targeted routing
-- Workers pass their agent_name and capabilities to filter tasks
CREATE OR REPLACE FUNCTION claim_next_task_run(
    p_worker_id TEXT,
    p_lease_duration_seconds INTEGER DEFAULT 600,
    p_worker_agent_name TEXT DEFAULT NULL,
    p_worker_capabilities JSONB DEFAULT '[]'::JSONB
)
RETURNS TABLE (
    run_id TEXT,
    task_id TEXT,
    user_id TEXT,
    priority INTEGER,
    target_agent_name TEXT,
    required_capabilities JSONB
) AS $$
DECLARE
    v_run task_runs%ROWTYPE;
BEGIN
    -- Find next queued job, respecting:
    -- 1. User concurrency limits
    -- 2. Agent-targeting rules (if task has target_agent_name, only that agent can claim it)
    -- 3. Capability requirements (worker must have ALL required capabilities)
    -- 4. Deadline expiration (skip tasks past deadline)
    -- Uses SKIP LOCKED to allow concurrent workers without blocking
    SELECT tr.* INTO v_run
    FROM task_runs tr
    LEFT JOIN users u ON tr.user_id = u.id
    WHERE tr.status = 'queued'
      AND (tr.lease_expires_at IS NULL OR tr.lease_expires_at < NOW())
      -- Deadline check: skip tasks past their deadline
      AND (tr.deadline_at IS NULL OR tr.deadline_at > NOW())
      -- Agent targeting: if task has target_agent_name, only that agent can claim it
      -- If task has no target, any worker can claim it
      AND (
          tr.target_agent_name IS NULL  -- No targeting = any worker
          OR tr.target_agent_name = p_worker_agent_name  -- Targeted at this worker
      )
      -- Capability check: worker must have ALL required capabilities
      -- Uses @> containment: worker_caps @> required_caps means "worker has all required"
      -- Note: required_capabilities is stored as JSONB array like '["cap1", "cap2"]'
      AND (
          tr.required_capabilities IS NULL  -- No requirements = any worker
          OR tr.required_capabilities = '[]'::JSONB  -- Empty array = any worker
          OR p_worker_capabilities @> tr.required_capabilities  -- Worker has all required caps
      )
      -- Check user hasn't hit concurrency limit (skip if no user)
      AND (
          tr.user_id IS NULL
          OR u.id IS NULL
          OR (
              SELECT COUNT(*) 
              FROM task_runs tr2 
              WHERE tr2.user_id = tr.user_id 
                AND tr2.status = 'running'
          ) < COALESCE(u.concurrency_limit, 999)
      )
    ORDER BY 
        -- Priority ordering: targeted tasks first (they're waiting for specific agent)
        CASE WHEN tr.target_agent_name IS NOT NULL THEN 0 ELSE 1 END,
        tr.priority DESC, 
        tr.created_at ASC
    FOR UPDATE SKIP LOCKED
    LIMIT 1;
    
    IF v_run.id IS NULL THEN
        RETURN;
    END IF;
    
    -- Claim the job
    UPDATE task_runs SET
        status = 'running',
        lease_owner = p_worker_id,
        lease_expires_at = NOW() + (p_lease_duration_seconds || ' seconds')::INTERVAL,
        started_at = COALESCE(started_at, NOW()),
        attempts = attempts + 1,
        updated_at = NOW()
    WHERE id = v_run.id;
    
    -- Return claimed job info
    run_id := v_run.id;
    task_id := v_run.task_id;
    user_id := v_run.user_id;
    priority := v_run.priority;
    target_agent_name := v_run.target_agent_name;
    required_capabilities := v_run.required_capabilities;
    RETURN NEXT;
END;
$$ LANGUAGE plpgsql;

-- Function to fail tasks that have exceeded their deadline
-- Run periodically (e.g., every 30 seconds) alongside reclaim_expired_task_runs
CREATE OR REPLACE FUNCTION fail_deadline_exceeded_tasks()
RETURNS INTEGER AS $$
DECLARE
    v_count INTEGER;
BEGIN
    UPDATE task_runs SET
        status = 'failed',
        routing_failed_at = NOW(),
        routing_failure_reason = 'Deadline exceeded: no matching worker claimed task before deadline',
        last_error = 'Deadline exceeded: no matching worker available',
        updated_at = NOW()
    WHERE status = 'queued'
      AND deadline_at IS NOT NULL
      AND deadline_at < NOW();
    
    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$ LANGUAGE plpgsql;

-- Update reclaim_expired_task_runs to preserve routing fields
-- (existing function already preserves them since we're only modifying status/lease columns)
-- But we should also check deadline when requeuing
CREATE OR REPLACE FUNCTION reclaim_expired_task_runs()
RETURNS INTEGER AS $$
DECLARE
    v_count INTEGER;
BEGIN
    -- First, fail any tasks that hit max attempts OR exceeded deadline
    UPDATE task_runs SET
        status = 'failed',
        lease_owner = NULL,
        lease_expires_at = NULL,
        last_error = CASE 
            WHEN attempts >= max_attempts THEN 'Max attempts exceeded (lease expired)'
            WHEN deadline_at IS NOT NULL AND deadline_at < NOW() THEN 'Deadline exceeded during retry'
            ELSE last_error
        END,
        routing_failed_at = CASE 
            WHEN deadline_at IS NOT NULL AND deadline_at < NOW() THEN NOW()
            ELSE routing_failed_at
        END,
        routing_failure_reason = CASE 
            WHEN deadline_at IS NOT NULL AND deadline_at < NOW() THEN 'Deadline exceeded during lease reclaim'
            ELSE routing_failure_reason
        END,
        updated_at = NOW()
    WHERE status = 'running'
      AND lease_expires_at < NOW()
      AND (attempts >= max_attempts OR (deadline_at IS NOT NULL AND deadline_at < NOW()));
    
    -- Then requeue tasks that can still retry
    UPDATE task_runs SET
        status = 'queued',
        lease_owner = NULL,
        lease_expires_at = NULL,
        last_error = 'Lease expired, requeued',
        updated_at = NOW()
    WHERE status = 'running'
      AND lease_expires_at < NOW()
      AND attempts < max_attempts
      AND (deadline_at IS NULL OR deadline_at > NOW());
    
    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$ LANGUAGE plpgsql;

-- View to see tasks waiting for specific agents
CREATE OR REPLACE VIEW targeted_task_queue AS
SELECT 
    target_agent_name,
    COUNT(*) as queued_count,
    MIN(created_at) as oldest_task,
    MAX(deadline_at) as nearest_deadline,
    AVG(EXTRACT(EPOCH FROM (NOW() - created_at)))::INTEGER as avg_wait_seconds
FROM task_runs
WHERE status = 'queued'
  AND target_agent_name IS NOT NULL
GROUP BY target_agent_name;

-- Comment explaining routing behavior
COMMENT ON COLUMN task_runs.target_agent_name IS 
    'If set, only workers with matching agent_name can claim this task. Task queues indefinitely until claimed or deadline_at expires.';
COMMENT ON COLUMN task_runs.required_capabilities IS 
    'JSON array of capability strings required to claim this task. Workers must have ALL listed capabilities.';
COMMENT ON COLUMN task_runs.deadline_at IS 
    'If set, task fails with routing_failure_reason if not claimed by this time. NULL = queue indefinitely.';
