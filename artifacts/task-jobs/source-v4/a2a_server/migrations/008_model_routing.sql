-- Migration: Model-aware Task Routing
-- Enables model_ref on tasks for explicit model selection
-- 
-- Design decisions:
-- 1. model_ref uses normalized provider:model format (e.g., "openai:gpt-4.1")
-- 2. Workers advertise models_supported array in claim call
-- 3. model_ref is stored on task_runs (not tasks) so retries preserve the original model
-- 4. NULL model_ref = any worker can claim (server/worker default applies)
-- 5. Workers with empty models_supported can only claim tasks with NULL model_ref

-- Add model_ref to task_runs
ALTER TABLE task_runs
    ADD COLUMN IF NOT EXISTS model_ref TEXT;

-- Index for model-targeted routing queries
-- Partial index since most tasks won't have explicit model_ref
CREATE INDEX IF NOT EXISTS idx_task_runs_model_ref 
    ON task_runs(model_ref) 
    WHERE model_ref IS NOT NULL;

-- Update claim_next_task_run to support model routing
-- Workers pass their models_supported array to filter tasks
CREATE OR REPLACE FUNCTION claim_next_task_run(
    p_worker_id TEXT,
    p_lease_duration_seconds INTEGER DEFAULT 600,
    p_worker_agent_name TEXT DEFAULT NULL,
    p_worker_capabilities JSONB DEFAULT '[]'::JSONB,
    p_worker_models_supported TEXT[] DEFAULT NULL
)
RETURNS TABLE (
    run_id TEXT,
    task_id TEXT,
    user_id TEXT,
    priority INTEGER,
    target_agent_name TEXT,
    required_capabilities JSONB,
    model_ref TEXT
) AS $$
DECLARE
    v_run task_runs%ROWTYPE;
BEGIN
    -- Find next queued job, respecting:
    -- 1. User concurrency limits
    -- 2. Agent-targeting rules (if task has target_agent_name, only that agent can claim it)
    -- 3. Capability requirements (worker must have ALL required capabilities)
    -- 4. Model requirements (if task has model_ref, worker must support that model)
    -- 5. Deadline expiration (skip tasks past deadline)
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
      -- Model check: if task has model_ref, worker must support that model
      -- NULL model_ref = any worker can claim (uses worker/server default)
      -- NULL/empty models_supported = worker can only claim NULL model_ref tasks
      AND (
          tr.model_ref IS NULL  -- No model requirement = any worker
          OR (
              p_worker_models_supported IS NOT NULL 
              AND array_length(p_worker_models_supported, 1) > 0
              AND tr.model_ref = ANY(p_worker_models_supported)
          )
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
        -- Then model-specific tasks (explicit model request)
        CASE WHEN tr.model_ref IS NOT NULL THEN 0 ELSE 1 END,
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
    model_ref := v_run.model_ref;
    RETURN NEXT;
END;
$$ LANGUAGE plpgsql;

-- View to see tasks waiting for specific models
CREATE OR REPLACE VIEW model_task_queue AS
SELECT 
    model_ref,
    COUNT(*) as queued_count,
    MIN(created_at) as oldest_task,
    MAX(deadline_at) as nearest_deadline,
    AVG(EXTRACT(EPOCH FROM (NOW() - created_at)))::INTEGER as avg_wait_seconds
FROM task_runs
WHERE status = 'queued'
  AND model_ref IS NOT NULL
GROUP BY model_ref;

-- Comment explaining model routing behavior
COMMENT ON COLUMN task_runs.model_ref IS 
    'Normalized model identifier (provider:model format, e.g., "openai:gpt-4.1"). If set, only workers supporting this model can claim the task. NULL = use worker/server default.';
