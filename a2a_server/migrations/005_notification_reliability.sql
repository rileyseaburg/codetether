-- Migration: Notification Reliability
-- Replaces boolean notification_sent with 3-state + retry tracking
-- Ensures emails are never permanently lost due to transient SendGrid failures

-- Replace notification_sent with proper status tracking
ALTER TABLE task_runs 
    DROP COLUMN IF EXISTS notification_sent;

-- Add notification status columns
ALTER TABLE task_runs
    ADD COLUMN IF NOT EXISTS notification_status TEXT DEFAULT 'none',  -- none, pending, sent, failed
    ADD COLUMN IF NOT EXISTS notification_attempts INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS notification_last_error TEXT,
    ADD COLUMN IF NOT EXISTS notification_next_retry_at TIMESTAMPTZ;

-- Add webhook notification status (separate from email)
ALTER TABLE task_runs
    ADD COLUMN IF NOT EXISTS webhook_status TEXT DEFAULT 'none',  -- none, pending, sent, failed
    ADD COLUMN IF NOT EXISTS webhook_attempts INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS webhook_last_error TEXT,
    ADD COLUMN IF NOT EXISTS webhook_next_retry_at TIMESTAMPTZ;

-- Index for retry queries (find failed notifications ready for retry)
CREATE INDEX IF NOT EXISTS idx_task_runs_notification_retry 
    ON task_runs(notification_status, notification_next_retry_at)
    WHERE notification_status = 'failed' AND notification_next_retry_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_task_runs_webhook_retry 
    ON task_runs(webhook_status, webhook_next_retry_at)
    WHERE webhook_status = 'failed' AND webhook_next_retry_at IS NOT NULL;

-- Index for pending notifications (just completed tasks needing notification)
CREATE INDEX IF NOT EXISTS idx_task_runs_notification_pending
    ON task_runs(notification_status, status)
    WHERE notification_status = 'pending';

-- Function to claim a notification for sending (atomic, prevents double-send)
CREATE OR REPLACE FUNCTION claim_notification_for_send(
    p_run_id TEXT,
    p_max_attempts INTEGER DEFAULT 3
)
RETURNS BOOLEAN AS $$
DECLARE
    v_claimed BOOLEAN;
BEGIN
    -- Atomically claim this notification by setting status to 'pending' and incrementing attempts
    -- Only claim if:
    -- 1. Status is 'none' (first attempt), or
    -- 2. Status is 'failed' AND next_retry_at <= now() AND attempts < max_attempts, or
    -- 3. Status is 'pending' AND updated_at is old (stuck claim from crashed worker)
    UPDATE task_runs SET
        notification_status = 'pending',
        notification_attempts = notification_attempts + 1,
        updated_at = NOW()
    WHERE id = p_run_id
      AND notify_email IS NOT NULL
      AND notification_status != 'sent'  -- Never re-send successful notifications
      AND notification_attempts < p_max_attempts
      AND (
          -- First attempt: notification never sent
          (notification_status = 'none' AND status IN ('completed', 'failed', 'needs_input'))
          OR
          -- Retry attempt: failed but eligible for retry
          (notification_status = 'failed' AND notification_next_retry_at <= NOW())
          OR
          -- Stuck claim: pending for > 5 minutes (worker likely crashed)
          (notification_status = 'pending' AND updated_at < NOW() - INTERVAL '5 minutes')
      );
    
    GET DIAGNOSTICS v_claimed = ROW_COUNT;
    RETURN v_claimed > 0;
END;
$$ LANGUAGE plpgsql;

-- Function to mark notification as sent
CREATE OR REPLACE FUNCTION mark_notification_sent(p_run_id TEXT)
RETURNS VOID AS $$
BEGIN
    UPDATE task_runs SET
        notification_status = 'sent',
        notification_last_error = NULL,
        notification_next_retry_at = NULL,
        updated_at = NOW()
    WHERE id = p_run_id;
END;
$$ LANGUAGE plpgsql;

-- Function to mark notification as failed with backoff
CREATE OR REPLACE FUNCTION mark_notification_failed(
    p_run_id TEXT,
    p_error TEXT,
    p_max_attempts INTEGER DEFAULT 3
)
RETURNS VOID AS $$
DECLARE
    v_attempts INTEGER;
    v_backoff_seconds INTEGER;
BEGIN
    -- Get current attempts
    SELECT notification_attempts INTO v_attempts FROM task_runs WHERE id = p_run_id;
    
    -- Calculate exponential backoff: 60s, 300s (5m), 900s (15m)
    v_backoff_seconds := LEAST(60 * POWER(5, COALESCE(v_attempts, 1) - 1), 900);
    
    UPDATE task_runs SET
        notification_status = CASE 
            WHEN COALESCE(v_attempts, 0) >= p_max_attempts THEN 'failed'  -- Permanent failure
            ELSE 'failed'  -- Retriable failure
        END,
        notification_last_error = p_error,
        notification_next_retry_at = CASE 
            WHEN COALESCE(v_attempts, 0) >= p_max_attempts THEN NULL  -- No more retries
            ELSE NOW() + (v_backoff_seconds || ' seconds')::INTERVAL
        END,
        updated_at = NOW()
    WHERE id = p_run_id;
END;
$$ LANGUAGE plpgsql;

-- Same functions for webhooks
CREATE OR REPLACE FUNCTION claim_webhook_for_send(
    p_run_id TEXT,
    p_max_attempts INTEGER DEFAULT 3
)
RETURNS BOOLEAN AS $$
DECLARE
    v_claimed BOOLEAN;
BEGIN
    UPDATE task_runs SET
        webhook_status = 'pending',
        webhook_attempts = webhook_attempts + 1,
        updated_at = NOW()
    WHERE id = p_run_id
      AND notify_webhook_url IS NOT NULL
      AND webhook_status != 'sent'
      AND webhook_attempts < p_max_attempts
      AND (
          (webhook_status = 'none' AND status IN ('completed', 'failed', 'needs_input'))
          OR
          (webhook_status = 'failed' AND webhook_next_retry_at <= NOW())
          OR
          (webhook_status = 'pending' AND updated_at < NOW() - INTERVAL '5 minutes')
      );
    
    GET DIAGNOSTICS v_claimed = ROW_COUNT;
    RETURN v_claimed > 0;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION mark_webhook_sent(p_run_id TEXT)
RETURNS VOID AS $$
BEGIN
    UPDATE task_runs SET
        webhook_status = 'sent',
        webhook_last_error = NULL,
        webhook_next_retry_at = NULL,
        updated_at = NOW()
    WHERE id = p_run_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION mark_webhook_failed(
    p_run_id TEXT,
    p_error TEXT,
    p_max_attempts INTEGER DEFAULT 3
)
RETURNS VOID AS $$
DECLARE
    v_attempts INTEGER;
    v_backoff_seconds INTEGER;
BEGIN
    SELECT webhook_attempts INTO v_attempts FROM task_runs WHERE id = p_run_id;
    v_backoff_seconds := LEAST(60 * POWER(5, COALESCE(v_attempts, 1) - 1), 900);
    
    UPDATE task_runs SET
        webhook_status = CASE 
            WHEN COALESCE(v_attempts, 0) >= p_max_attempts THEN 'failed'
            ELSE 'failed'
        END,
        webhook_last_error = p_error,
        webhook_next_retry_at = CASE 
            WHEN COALESCE(v_attempts, 0) >= p_max_attempts THEN NULL
            ELSE NOW() + (v_backoff_seconds || ' seconds')::INTERVAL
        END,
        updated_at = NOW()
    WHERE id = p_run_id;
END;
$$ LANGUAGE plpgsql;

-- Function to get notifications ready for retry (includes stuck 'pending' from crashed workers)
CREATE OR REPLACE FUNCTION get_pending_notification_retries(p_limit INTEGER DEFAULT 10)
RETURNS TABLE (
    run_id TEXT,
    task_id TEXT,
    notify_email TEXT,
    notify_webhook_url TEXT,
    notification_status TEXT,
    notification_attempts INTEGER,
    webhook_status TEXT,
    webhook_attempts INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        tr.id as run_id,
        tr.task_id,
        tr.notify_email,
        tr.notify_webhook_url,
        tr.notification_status,
        tr.notification_attempts,
        tr.webhook_status,
        tr.webhook_attempts
    FROM task_runs tr
    WHERE 
        -- Email needs retry (failed or stuck pending)
        (tr.notify_email IS NOT NULL AND (
            (tr.notification_status = 'failed' AND tr.notification_next_retry_at <= NOW())
            OR (tr.notification_status = 'pending' AND tr.updated_at < NOW() - INTERVAL '5 minutes')
        ))
        OR
        -- Webhook needs retry (failed or stuck pending)
        (tr.notify_webhook_url IS NOT NULL AND (
            (tr.webhook_status = 'failed' AND tr.webhook_next_retry_at <= NOW())
            OR (tr.webhook_status = 'pending' AND tr.updated_at < NOW() - INTERVAL '5 minutes')
        ))
    ORDER BY 
        LEAST(
            COALESCE(tr.notification_next_retry_at, tr.updated_at, 'infinity'::timestamptz),
            COALESCE(tr.webhook_next_retry_at, tr.updated_at, 'infinity'::timestamptz)
        ) ASC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Update task_queue_status view to include notification stats
DROP VIEW IF EXISTS task_queue_status;
CREATE VIEW task_queue_status AS
SELECT 
    status,
    COUNT(*) as count,
    AVG(EXTRACT(EPOCH FROM (NOW() - created_at)))::INTEGER as avg_wait_seconds,
    MAX(EXTRACT(EPOCH FROM (NOW() - created_at)))::INTEGER as max_wait_seconds,
    COUNT(*) FILTER (WHERE notification_status = 'sent') as notifications_sent,
    COUNT(*) FILTER (WHERE notification_status = 'failed' AND notification_next_retry_at IS NULL) as notifications_permanently_failed,
    COUNT(*) FILTER (WHERE notification_status = 'failed' AND notification_next_retry_at IS NOT NULL) as notifications_pending_retry
FROM task_runs
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY status;

-- Comment explaining the notification flow
COMMENT ON COLUMN task_runs.notification_status IS 
'Notification status: none (no email configured), pending (being sent), sent (delivered), failed (error, check notification_last_error)';

COMMENT ON COLUMN task_runs.notification_next_retry_at IS 
'When to retry failed notification. NULL = no more retries (max attempts reached or success)';
