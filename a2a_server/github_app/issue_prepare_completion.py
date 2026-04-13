"""Follow-up creation for GitHub App issue prepare tasks."""

from .settings import MODEL_REF
from .task_context import issue_task_context
from .watch import post_issue_comment


async def handle_issue_prepare_completion(task: dict, worker_id: str | None = None) -> None:
    """Create the issue build task or post a prepare failure."""
    from ..monitor_api import AgentTaskCreate, create_agent_task

    metadata = task.get('metadata') or {}
    context = await issue_task_context(task)
    if context is None:
        return
    repo, issue_number, _, token = context
    if str(task.get('status')) != 'completed':
        body = str(task.get('error') or task.get('result') or f"Task `{task.get('id')}` ended with status `{task.get('status')}`.").strip()
        await post_issue_comment(repo, issue_number, token, f"## 🛠️ CodeTether Fix\n\nI couldn't prepare the issue workspace.\n\n{body}")
        return
    followup = metadata.get('post_clone_task') or {}
    workspace_id = str(metadata.get('workspace_id') or '').strip()
    prompt = str(followup.get('prompt') or '').strip()
    if not workspace_id or not prompt:
        await post_issue_comment(repo, issue_number, token, "## 🛠️ CodeTether Fix\n\nI prepared the workspace, but the follow-up task metadata was incomplete.")
        return
    followup_metadata = dict(followup.get('metadata') or {})
    target_worker_id = str(worker_id or task.get('worker_id') or '').strip()
    if target_worker_id:
        followup_metadata['target_worker_id'] = target_worker_id
    await create_agent_task(workspace_id, AgentTaskCreate(title=str(followup.get('title') or f'Work issue #{issue_number}'), prompt=prompt, agent_type=str(followup.get('agent_type') or 'build'), metadata=followup_metadata, model_ref=MODEL_REF))
