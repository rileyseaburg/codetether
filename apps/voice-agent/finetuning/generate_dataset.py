"""Script to generate training examples for FunctionGemma fine-tuning.

This script uses templates and variations to programmatically generate diverse
training examples for the CodeTether tools in FunctionGemma format.
"""

import json
import random
from typing import Any, Dict, List


TASK_TITLE_TEMPLATES = [
    'fix {issue}',
    'implement {feature}',
    'add {feature}',
    'update {component}',
    'refactor {component}',
    'remove {feature}',
    'optimize {component}',
    'debug {issue}',
    'test {component}',
    'document {feature}',
    'improve {aspect}',
    'create {feature}',
    'fix bug in {component}',
    'add support for {feature}',
    'update documentation for {component}',
    'improve performance of {component}',
    'write tests for {component}',
    'review {component}',
    'cleanup {component}',
    'migrate {component}',
]

ISSUE_TEMPLATES = [
    'login bug',
    'authentication issue',
    'memory leak',
    'security vulnerability',
    'performance problem',
    'crash bug',
    'typo',
    'layout issue',
    'timeout error',
    'connection problem',
    'data corruption',
    'race condition',
    'null pointer exception',
    'syntax error',
    'configuration issue',
    'compatibility problem',
]

FEATURE_TEMPLATES = [
    'user authentication',
    'API endpoint',
    'database query',
    'user interface',
    'logging system',
    'caching layer',
    'search functionality',
    'notification system',
    'payment integration',
    'email service',
    'file upload',
    'data export',
    'user profile',
    'dashboard',
    'admin panel',
    'search filter',
    'sorting feature',
    'pagination',
    'error handling',
    'input validation',
]

COMPONENT_TEMPLATES = [
    'payment module',
    'user service',
    'database layer',
    'API gateway',
    'frontend app',
    'backend API',
    'authentication service',
    'cache system',
    'logging module',
    'notification service',
    'file handler',
    'data processor',
    'session manager',
    'config loader',
    'utility functions',
    'data models',
    'controller',
    'middleware',
    'repository',
    'service layer',
]

ASPECT_TEMPLATES = [
    'performance',
    'security',
    'usability',
    'reliability',
    'maintainability',
    'testability',
    'accessibility',
    'compatibility',
    'scalability',
    'code quality',
]

DESCRIPTION_TEMPLATES = [
    'The {component} has a {issue} that needs to be fixed',
    'We need to add {feature} to improve the system',
    'Implement {feature} to support new requirements',
    'Fix the {issue} in the {component}',
    'Add {feature} functionality to the system',
    'Update {component} to support new use cases',
    'Refactor {component} for better maintainability',
    'Optimize {component} for improved performance',
    'Add comprehensive tests for {component}',
    'Update documentation for {feature}',
]

SESSION_ID_TEMPLATES = [
    'session-{random}',
    'chat-{random}',
    'conversation-{random}',
    'meeting-{random}',
    'discussion-{random}',
]

TASK_ID_TEMPLATES = [
    'task-{random}',
    'task-{random_id}',
    '{random_id}',
    'job-{random}',
    'item-{random}',
]

CODEBASE_ID_TEMPLATES = [
    'my-project',
    'backend-api',
    'frontend-app',
    'mobile-app',
    'data-pipeline',
    'ml-models',
    'infrastructure',
    'documentation',
    'tests',
    'scripts',
]

AGENT_NAME_TEMPLATES = [
    'builder-agent',
    'planner-agent',
    'test-agent',
    'reviewer-agent',
    'explorer-agent',
    'general-agent',
    'deployment-agent',
    'documentation-agent',
    'code-agent',
    'devops-agent',
]

MESSAGE_TEMPLATES = [
    'Please {action}',
    'I need you to {action}',
    'Could you {action}',
    'Can you {action}',
    'Please handle {task}',
    'Start working on {task}',
    'Continue with {task}',
    'Finish {task}',
    'Check the {component}',
    'Review the {codebase}',
    'Run tests on {codebase}',
    'Deploy the new version',
    'Analyze the performance',
    'Investigate the issue',
]

ACTION_TEMPLATES = [
    'implement the new feature',
    'fix the bug',
    'write tests',
    'update documentation',
    'refactor the code',
    'optimize performance',
    'check the logs',
    'review the code',
    'run the build',
    'deploy to production',
    'analyze the data',
    'clean up the codebase',
    'add error handling',
    'update dependencies',
    'create a report',
]

TASK_TEMPLATES = [
    'the refactoring task',
    'the new feature implementation',
    'the bug fix',
    'the documentation update',
    'the test suite',
    'the optimization task',
    'the code review',
    'the deployment',
    'the investigation',
]

random.seed(42)


def generate_random_id(length: int = 6) -> str:
    """Generate a random alphanumeric ID."""
    chars = 'abcdefghijklmnopqrstuvwxyz0123456789'
    return ''.join(random.choice(chars) for _ in range(length))


def generate_random_number(length: int = 4) -> str:
    """Generate a random numeric ID."""
    digits = '0123456789'
    if length == 1:
        return random.choice('123456789')
    result = random.choice('123456789') + ''.join(
        random.choice(digits) for _ in range(length - 1)
    )
    return result


def format_function_call(tool_name: str, args: Dict[str, str]) -> str:
    """Format a function call in FunctionGemma format."""
    args_str = ''
    for key, value in args.items():
        args_str += f'{key}:<escape>{value}<escape>,'
    args_str = args_str.rstrip(',')
    return f'<start_function_call>call:{tool_name}{{{args_str}}}<end_function_call>'


def generate_create_task_examples(count: int = 50) -> List[Dict[str, str]]:
    """Generate training examples for create_task tool."""
    examples = []
    agent_types = ['build', 'plan', 'general', 'explore']
    priorities = [1, 2, 3, 5, 7, 8, 10]

    action_verbs = [
        'Create',
        'Add',
        'Make',
        'I need',
        "I'd like",
        'Can you',
        'Please',
        'I want',
        "Let's create",
        'We should create',
        'I would like to create',
        'Could you create',
        'Will you create',
        'Set up a task for',
    ]

    for _ in range(count):
        title_template = random.choice(TASK_TITLE_TEMPLATES)
        title_issue = random.choice(ISSUE_TEMPLATES)
        title_feature = random.choice(FEATURE_TEMPLATES)
        title_component = random.choice(COMPONENT_TEMPLATES)
        title_aspect = random.choice(ASPECT_TEMPLATES)

        title = title_template.format(
            issue=title_issue,
            feature=title_feature,
            component=title_component,
            aspect=title_aspect,
        )

        description_template = random.choice(DESCRIPTION_TEMPLATES)
        description = description_template.format(
            component=random.choice(COMPONENT_TEMPLATES),
            issue=random.choice(ISSUE_TEMPLATES),
            feature=random.choice(FEATURE_TEMPLATES),
        )

        has_description = random.random() > 0.3
        has_codebase = random.random() > 0.4
        has_agent_type = random.random() > 0.5
        has_priority = random.random() > 0.6

        args = {'title': title}
        if has_description:
            args['description'] = description
        if has_codebase:
            args['codebase_id'] = random.choice(CODEBASE_ID_TEMPLATES)
        if has_agent_type:
            args['agent_type'] = random.choice(agent_types)
        if has_priority:
            args['priority'] = str(random.choice(priorities))

        input_variations = [
            f'{verb} a task to {title.lower()}',
            f'{verb} a task for {title.lower()}',
            f'{verb} new task: {title.lower()}',
            f'{verb} task titled: {title.lower()}',
            f'I want to {title.lower()}',
            f'I need to {title.lower()}',
            f'Can you {title.lower()} as a task',
            f'Please create a task for: {title.lower()}',
            f'Create task: {title.lower()}',
        ]

        if has_description:
            input_variations.extend(
                [
                    f'Create task to {title.lower()} with description: {description.lower()}',
                    f"Create a task titled '{title}' with description: {description}",
                ]
            )

        if has_priority and has_agent_type:
            input_variations.extend(
                [
                    f'Create a high priority {random.choice(agent_types)} task to {title.lower()}',
                    f'Create a {random.choice(agent_types)} task with priority {random.choice(priorities)} for {title.lower()}',
                ]
            )

        if has_codebase and has_agent_type:
            input_variations.extend(
                [
                    f'Create a {random.choice(agent_types)} task for {random.choice(CODEBASE_ID_TEMPLATES)} codebase titled: {title.lower()}',
                ]
            )

        user_input = random.choice(input_variations)
        output = format_function_call('create_task', args)

        examples.append({'input': user_input, 'output': output})

    return examples


def generate_list_tasks_examples(count: int = 30) -> List[Dict[str, str]]:
    """Generate training examples for list_tasks tool."""
    examples = []
    statuses = ['pending', 'running', 'completed', 'failed', 'cancelled']
    codebase_ids = CODEBASE_ID_TEMPLATES + ['global']

    question_words = ['What', 'Show', 'List', 'Give me', 'Tell me']
    verbs = ['show', 'list', 'display', 'get', 'retrieve']
    start_phrases = [
        '',
        'Can you ',
        'Please ',
        'I want to ',
        'Could you ',
        "I'd like to ",
    ]

    for _ in range(count):
        has_status = random.random() > 0.3
        has_codebase = random.random() > 0.4

        status = random.choice(statuses) if has_status else None
        codebase_id = random.choice(codebase_ids) if has_codebase else None

        args = {}
        if status:
            args['status'] = status
        if codebase_id:
            args['codebase_id'] = codebase_id

        if status and codebase_id:
            input_variations = [
                f'{verb} {status} tasks for {codebase_id}',
                f'{verb} all {status} tasks in {codebase_id}',
                f'Show me {status} tasks from {codebase_id}',
                f'What {status} tasks do we have in {codebase_id}',
                f'List the {status} tasks for codebase {codebase_id}',
            ]
        elif status:
            input_variations = [
                f'{verb} all {status} tasks',
                f'Show me {status} tasks',
                f'What {status} tasks are there',
                f'List {status} tasks',
                f'Give me the list of {status} tasks',
                f'What tasks are {status}',
                f'Show tasks with {status} status',
            ]
        elif codebase_id:
            input_variations = [
                f'{verb} tasks for {codebase_id}',
                f'Show me tasks in {codebase_id}',
                f'What tasks are in {codebase_id}',
                f'List all tasks for {codebase_id}',
                f'Show me all tasks from {codebase_id}',
            ]
        else:
            input_variations = [
                f'{verb} all tasks',
                f'Show me all tasks',
                f'What tasks do we have',
                f'List all tasks',
                f'Give me the list of all tasks',
                f'What tasks are there',
                f'Show me everything',
            ]

        verb = random.choice(verbs)
        input_variations = [v.replace('{verb}', verb) for v in input_variations]
        start_phrase = random.choice(start_phrases)
        if start_phrase and not any(
            input_variations[0].lower().startswith(x)
            for x in ['what', 'show', 'list', 'can']
        ):
            user_input = start_phrase + input_variations[0]
        else:
            user_input = random.choice(input_variations)

        user_input = (
            user_input[0].upper() + user_input[1:] if user_input else user_input
        )

        output = format_function_call('list_tasks', args)

        examples.append({'input': user_input, 'output': output})

    return examples


def generate_get_task_examples(count: int = 30) -> List[Dict[str, str]]:
    """Generate training examples for get_task tool."""
    examples = []

    verbs = ['get', 'show', 'display', 'retrieve', 'fetch']
    question_prefixes = [
        "What's the status of",
        'What is',
        'Tell me about',
        'Give me details on',
    ]
    request_phrases = [
        'I need to see',
        'I want to see',
        'Can you show me',
        'Please show me',
    ]

    for _ in range(count):
        task_id = f'task-{generate_random_id()}'
        args = {'task_id': task_id}

        input_variations = [
            f'{verb} task {task_id}',
            f'{verb} details for {task_id}',
            f'{verb} information about {task_id}',
            f'Show me task {task_id}',
            f'Tell me about task {task_id}',
            f'What is task {task_id}',
            f"What's the status of {task_id}",
            f'I need to see task {task_id}',
            f'I want to see the details of {task_id}',
            f'Can you show me what {task_id} is doing',
        ]

        verb = random.choice(verbs)
        input_variations = [v.replace('{verb}', verb) for v in input_variations]
        user_input = random.choice(input_variations)

        output = format_function_call('get_task', args)

        examples.append({'input': user_input, 'output': output})

    return examples


def generate_cancel_task_examples(count: int = 25) -> List[Dict[str, str]]:
    """Generate training examples for cancel_task tool."""
    examples = []

    verbs = ['cancel', 'stop', 'abort', 'terminate', 'kill']
    request_phrases = [
        'I need to',
        'I want to',
        'Can you',
        'Please',
        "I'd like to",
    ]

    for _ in range(count):
        task_id = f'task-{generate_random_id()}'
        args = {'task_id': task_id}

        input_variations = [
            f'{verb} task {task_id}',
            f'{verb} {task_id}',
            f'Stop running task {task_id}',
            f'Cancel the task {task_id}',
            f'Abort task {task_id}',
            f'I need to cancel {task_id}',
            f'I want to stop {task_id}',
            f'Can you terminate {task_id}',
            f'Please kill task {task_id}',
            f'Stop the task {task_id} from running',
            f'Cancel my task {task_id}',
        ]

        verb = random.choice(verbs)
        input_variations = [v.replace('{verb}', verb) for v in input_variations]

        if random.random() > 0.5:
            prefix = random.choice(request_phrases)
            input_variations.append(f'{prefix} {input_variations[0].lower()}')

        user_input = random.choice(input_variations)

        output = format_function_call('cancel_task', args)

        examples.append({'input': user_input, 'output': output})

    return examples


def generate_get_session_history_examples(
    count: int = 20,
) -> List[Dict[str, str]]:
    """Generate training examples for get_session_history tool."""
    examples = []

    verbs = ['show', 'get', 'retrieve', 'fetch', 'display']
    question_phrases = [
        'What happened in',
        'What was discussed in',
        'What occurred in',
    ]
    request_phrases = ['I need to see', 'I want to see', 'Can you show me']

    for _ in range(count):
        session_id = f'session-{generate_random_id()}'
        args = {'session_id': session_id}

        input_variations = [
            f'{verb} session history for {session_id}',
            f'{verb} the session history {session_id}',
            f'Show me the history for session {session_id}',
            f'What happened in session {session_id}',
            f'What was discussed in {session_id}',
            f'Retrieve conversation history for {session_id}',
            f'I need to see the session history of {session_id}',
            f'Can you show me what we talked about in {session_id}',
            f'Get the message history for session {session_id}',
            f'What occurred during session {session_id}',
        ]

        verb = random.choice(verbs)
        input_variations = [v.replace('{verb}', verb) for v in input_variations]
        user_input = random.choice(input_variations)

        output = format_function_call('get_session_history', args)

        examples.append({'input': user_input, 'output': output})

    return examples


def generate_discover_agents_examples(count: int = 15) -> List[Dict[str, str]]:
    """Generate training examples for discover_agents tool."""
    examples = []

    verbs = ['show', 'list', 'display', 'discover']
    question_phrases = ['What', 'Which']
    request_phrases = [
        'Tell me',
        'Show me',
        'I want to know',
        'Can you tell me',
    ]

    for _ in range(count):
        input_variations = [
            f'{verb} available agents',
            f'{verb} all agents',
            f'{verb} what agents are available',
            f'What agents are available',
            f'Which agents can I use',
            f'What agents are there',
            f'List all available agents',
            f'Show me the agents I can use',
            f'Tell me what agents are available',
            f'What agents can I assign tasks to',
            f'Which agents are registered in the system',
            f'I want to see the available agents',
            f'Can you list the agents I can message',
        ]

        verb = random.choice(verbs)
        input_variations = [v.replace('{verb}', verb) for v in input_variations]

        if random.random() > 0.5:
            prefix = random.choice(request_phrases)
            if not any(
                input_variations[0].lower().startswith(x)
                for x in ['what', 'which', 'tell']
            ):
                input_variations.append(
                    f'{prefix.lower()} {input_variations[0].lower()}'
                )

        user_input = random.choice(input_variations)

        output = format_function_call('discover_agents', {})

        examples.append({'input': user_input, 'output': output})

    return examples


def generate_send_message_examples(count: int = 25) -> List[Dict[str, str]]:
    """Generate training examples for send_message tool."""
    examples = []

    agent_names = AGENT_NAME_TEMPLATES
    actions = ACTION_TEMPLATES
    tasks = TASK_TEMPLATES

    for _ in range(count):
        agent_name = random.choice(agent_names)
        message = random.choice(MESSAGE_TEMPLATES).format(
            action=random.choice(actions),
            task=random.choice(tasks),
            component=random.choice(COMPONENT_TEMPLATES),
            codebase=random.choice(CODEBASE_ID_TEMPLATES),
        )

        args = {'agent_name': agent_name, 'message': message}

        input_variations = [
            f'Send message to {agent_name}: {message}',
            f'Message {agent_name} to {message.lower()}',
            f'Tell {agent_name} to {message.lower()}',
            f'Send to {agent_name}: {message}',
            f'{agent_name}, please {message.lower()}',
            f'Hey {agent_name}, {message.lower()}',
            f'Can you message {agent_name} about {message.lower()}',
            f'Please send this message to {agent_name}: {message}',
            f'I want to send a message to {agent_name}: {message}',
            f'Message {agent_name} saying {message}',
        ]

        user_input = random.choice(input_variations)

        output = format_function_call('send_message', args)

        examples.append({'input': user_input, 'output': output})

    return examples


def generate_playback_session_examples(count: int = 15) -> List[Dict[str, str]]:
    """Generate training examples for playback_session tool."""
    examples = []

    verbs = ['play back', 'playback', 'replay', 'show']
    styles = ['verbatim', 'summary']

    for _ in range(count):
        session_id = f'session-{generate_random_id()}'
        has_style = random.random() > 0.5

        args = {'session_id': session_id}
        if has_style:
            style = random.choice(styles)
            args['style'] = style

        if has_style:
            input_variations = [
                f'{verb} session {session_id} in {style} format',
                f'{verb} {session_id} as {style}',
                f'Play back session {session_id} in {style} style',
                f'Show me session {session_id} as a {style}',
                f'I want to see {session_id} in {style} format',
            ]
        else:
            input_variations = [
                f'{verb} session {session_id}',
                f'{verb} {session_id}',
                f'Play back session {session_id}',
                f'Replay session {session_id}',
                f'Show me session {session_id}',
            ]

        verb = random.choice(verbs)
        input_variations = [v.replace('{verb}', verb) for v in input_variations]
        user_input = random.choice(input_variations)

        output = format_function_call('playback_session', args)

        examples.append({'input': user_input, 'output': output})

    return examples


def generate_dataset(
    create_task_count: int = 50,
    list_tasks_count: int = 30,
    get_task_count: int = 30,
    cancel_task_count: int = 25,
    get_session_history_count: int = 20,
    discover_agents_count: int = 15,
    send_message_count: int = 25,
    playback_session_count: int = 15,
    output_path: str = 'training_examples.jsonl',
) -> List[Dict[str, str]]:
    """Generate a complete training dataset and save to file.

    Args:
        create_task_count: Number of create_task examples to generate
        list_tasks_count: Number of list_tasks examples to generate
        get_task_count: Number of get_task examples to generate
        cancel_task_count: Number of cancel_task examples to generate
        get_session_history_count: Number of get_session_history examples to generate
        discover_agents_count: Number of discover_agents examples to generate
        send_message_count: Number of send_message examples to generate
        playback_session_count: Number of playback_session examples to generate
        output_path: Path to save the JSONL file

    Returns:
        List of all generated examples
    """
    all_examples = []

    print(f'Generating {create_task_count} create_task examples...')
    all_examples.extend(generate_create_task_examples(create_task_count))

    print(f'Generating {list_tasks_count} list_tasks examples...')
    all_examples.extend(generate_list_tasks_examples(list_tasks_count))

    print(f'Generating {get_task_count} get_task examples...')
    all_examples.extend(generate_get_task_examples(get_task_count))

    print(f'Generating {cancel_task_count} cancel_task examples...')
    all_examples.extend(generate_cancel_task_examples(cancel_task_count))

    print(
        f'Generating {get_session_history_count} get_session_history examples...'
    )
    all_examples.extend(
        generate_get_session_history_examples(get_session_history_count)
    )

    print(f'Generating {discover_agents_count} discover_agents examples...')
    all_examples.extend(
        generate_discover_agents_examples(discover_agents_count)
    )

    print(f'Generating {send_message_count} send_message examples...')
    all_examples.extend(generate_send_message_examples(send_message_count))

    print(f'Generating {playback_session_count} playback_session examples...')
    all_examples.extend(
        generate_playback_session_examples(playback_session_count)
    )

    random.shuffle(all_examples)

    print(f'Writing {len(all_examples)} examples to {output_path}...')
    with open(output_path, 'w') as f:
        for example in all_examples:
            f.write(json.dumps(example) + '\n')

    print(f'Dataset generated successfully with {len(all_examples)} examples')

    return all_examples


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='Generate FunctionGemma training dataset'
    )
    parser.add_argument(
        '--create-task',
        type=int,
        default=50,
        help='Number of create_task examples',
    )
    parser.add_argument(
        '--list-tasks',
        type=int,
        default=30,
        help='Number of list_tasks examples',
    )
    parser.add_argument(
        '--get-task', type=int, default=30, help='Number of get_task examples'
    )
    parser.add_argument(
        '--cancel-task',
        type=int,
        default=25,
        help='Number of cancel_task examples',
    )
    parser.add_argument(
        '--session-history',
        type=int,
        default=20,
        help='Number of get_session_history examples',
    )
    parser.add_argument(
        '--discover-agents',
        type=int,
        default=15,
        help='Number of discover_agents examples',
    )
    parser.add_argument(
        '--send-message',
        type=int,
        default=25,
        help='Number of send_message examples',
    )
    parser.add_argument(
        '--playback-session',
        type=int,
        default=15,
        help='Number of playback_session examples',
    )
    parser.add_argument(
        '--output',
        type=str,
        default='training_examples.jsonl',
        help='Output file path',
    )

    args = parser.parse_args()

    generate_dataset(
        create_task_count=args.create_task,
        list_tasks_count=args.list_tasks,
        get_task_count=args.get_task,
        cancel_task_count=args.cancel_task,
        get_session_history_count=args.session_history,
        discover_agents_count=args.discover_agents,
        send_message_count=args.send_message,
        playback_session_count=args.playback_session,
        output_path=args.output,
    )
