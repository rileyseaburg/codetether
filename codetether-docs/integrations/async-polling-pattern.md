# Async Polling Pattern

Use GET `/v1/automation/tasks/{task_id}` to poll for task status.

## Status Values
- `queued` - Waiting to be processed
- `running` - Currently executing
- `needs_input` - Requires user input
- `completed` - Finished successfully
- `failed` - Task failed
- `cancelled` - Task cancelled

## Polling Loop

```javascript
while (retryCount < maxRetries) {
  const response = await fetch(`/tasks/${taskId}`);
  const data = await response.json();

  if (['completed', 'failed', 'cancelled'].includes(data.status)) {
    return data;
  }

  await sleep(5000);
}
```

## Platform Examples

**n8n:** Split in Batches → HTTP Request → Sleep → Filter (status check) → Loop

**Make:** Iterator → Sleep → HTTP Request → Array Aggregator
