import ast
from pathlib import Path

from a2a_server.github_app.settings import TASK_PRIORITY


GITHUB_APP_DIR = Path(__file__).parents[1] / 'a2a_server' / 'github_app'


def test_github_app_task_priority_is_high_and_positive():
    assert TASK_PRIORITY == 100


def test_every_github_app_dispatch_uses_shared_priority():
    dispatches = []
    missing_priority = []

    for path in sorted(GITHUB_APP_DIR.glob('*.py')):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            function_name = getattr(node.func, 'id', None) or getattr(
                node.func, 'attr', None
            )
            if function_name != 'create_and_dispatch_task':
                continue
            dispatches.append(f'{path.name}:{node.lineno}')
            priority = next(
                (
                    keyword.value
                    for keyword in node.keywords
                    if keyword.arg == 'priority'
                ),
                None,
            )
            if not (
                isinstance(priority, ast.Name)
                and priority.id == 'TASK_PRIORITY'
            ):
                missing_priority.append(f'{path.name}:{node.lineno}')

    assert len(dispatches) == 9
    assert missing_priority == []
