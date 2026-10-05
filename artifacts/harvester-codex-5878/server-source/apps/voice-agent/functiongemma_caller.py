"""FunctionGemma caller module for local function calling inference.

This module provides integration with Google's FunctionGemma model
(google/functiongemma-270m-it) for parsing user intent into structured
function calls for the CodeTether voice agent system.

The module implements lazy loading of the model to ensure efficient
resource usage, loading the model only when first needed.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

CODETETHER_TOOLS: List[Dict[str, Any]] = [
    {
        'name': 'create_task',
        'description': 'Create a new task for an agent to execute',
        'parameters': {
            'type': 'object',
            'properties': {
                'title': {
                    'type': 'string',
                    'description': 'The title of the task',
                },
                'description': {
                    'type': 'string',
                    'description': 'Detailed description of what the task should accomplish',
                },
                'codebase_id': {
                    'type': 'string',
                    'description': 'Optional identifier for the codebase context',
                },
                'agent_type': {
                    'type': 'string',
                    'enum': ['build', 'plan', 'general', 'explore'],
                    'description': 'The type of agent to handle this task',
                },
                'priority': {
                    'type': 'integer',
                    'description': 'Task priority (higher values indicate higher priority)',
                },
            },
            'required': ['title'],
        },
    },
    {
        'name': 'list_tasks',
        'description': 'List tasks with optional filtering',
        'parameters': {
            'type': 'object',
            'properties': {
                'status': {
                    'type': 'string',
                    'description': 'Filter tasks by status',
                },
                'codebase_id': {
                    'type': 'string',
                    'description': 'Filter tasks by codebase identifier',
                },
            },
        },
    },
    {
        'name': 'get_task',
        'description': 'Retrieve details of a specific task',
        'parameters': {
            'type': 'object',
            'properties': {
                'task_id': {
                    'type': 'string',
                    'description': 'The unique identifier of the task',
                },
            },
            'required': ['task_id'],
        },
    },
    {
        'name': 'cancel_task',
        'description': 'Cancel an active task',
        'parameters': {
            'type': 'object',
            'properties': {
                'task_id': {
                    'type': 'string',
                    'description': 'The unique identifier of the task to cancel',
                },
            },
            'required': ['task_id'],
        },
    },
    {
        'name': 'get_session_history',
        'description': 'Retrieve the message history for a session',
        'parameters': {
            'type': 'object',
            'properties': {
                'session_id': {
                    'type': 'string',
                    'description': 'The unique identifier of the session',
                },
            },
            'required': ['session_id'],
        },
    },
    {
        'name': 'playback_session',
        'description': 'Play back a session with optional summarization',
        'parameters': {
            'type': 'object',
            'properties': {
                'session_id': {
                    'type': 'string',
                    'description': 'The unique identifier of the session to playback',
                },
                'style': {
                    'type': 'string',
                    'enum': ['verbatim', 'summary'],
                    'description': 'The playback style to use',
                },
            },
            'required': ['session_id'],
        },
    },
    {
        'name': 'discover_agents',
        'description': 'Discover available agents in the system',
        'parameters': {
            'type': 'object',
            'properties': {},
        },
    },
    {
        'name': 'send_message',
        'description': 'Send a message to a specific agent',
        'parameters': {
            'type': 'object',
            'properties': {
                'agent_name': {
                    'type': 'string',
                    'description': 'The name of the target agent',
                },
                'message': {
                    'type': 'string',
                    'description': 'The message content to send',
                },
            },
            'required': ['agent_name', 'message'],
        },
    },
]


class FunctionGemmaCaller:
    """Caller for FunctionGemma model for local function calling inference.

    This class provides an interface to the FunctionGemma model for parsing
    natural language user input into structured function calls. It uses lazy
    loading to defer model initialization until first use.

    Attributes:
        model_path: Path to the FunctionGemma model (default: google/functiongemma-270m-it)
        _model: The loaded model instance (None until first call)
        _processor: The loaded processor instance (None until first call)
    """

    def __init__(
        self, model_path: str = 'google/functiongemma-270m-it'
    ) -> None:
        """Initialize the FunctionGemma caller.

        Args:
            model_path: Path to the FunctionGemma model. Can be a HuggingFace
                model ID or a local path. Defaults to "google/functiongemma-270m-it".
        """
        self.model_path = model_path
        self._model: Optional[Any] = None
        self._processor: Optional[Any] = None

    def _load_model(self) -> None:
        """Load the FunctionGemma model and processor.

        This method performs lazy loading of the model and processor on first
        use. The model is loaded in BF16 precision with automatic device mapping.

        Raises:
            RuntimeError: If the model fails to load.
        """
        if self._model is not None and self._processor is not None:
            return

        try:
            # Delay heavy ML imports until first intent parse so worker process
            # startup stays fast and avoids LiveKit process-init timeouts.
            import torch
            from transformers import AutoModelForCausalLM, AutoProcessor

            logger.info(f'Loading FunctionGemma model from {self.model_path}')
            self._processor = AutoProcessor.from_pretrained(
                self.model_path,
                trust_remote_code=True,
            )
            self._model = AutoModelForCausalLM.from_pretrained(
                self.model_path,
                torch_dtype=torch.bfloat16,
                device_map='auto',
                trust_remote_code=True,
            )
            logger.info('FunctionGemma model loaded successfully')
        except Exception as e:
            logger.error(f'Failed to load FunctionGemma model: {e}')
            raise RuntimeError(
                f'Failed to load FunctionGemma model: {e}'
            ) from e

    async def parse_intent(self, user_input: str) -> Optional[Dict[str, Any]]:
        """Parse user input into a structured function call.

        This method takes natural language input from the user and uses
        FunctionGemma to generate a structured function call.

        Args:
            user_input: The natural language input from the user.

        Returns:
            A dictionary containing the function name and arguments if a
            function call is successfully parsed, None otherwise.
        """
        self._load_model()

        if self._model is None or self._processor is None:
            logger.error('Model not loaded after _load_model() call')
            return None

        try:
            messages = [
                {
                    'role': 'user',
                    'content': user_input,
                },
            ]

            input_text = self._processor.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )

            inputs = self._processor(
                input_text,
                return_tensors='pt',
            ).to(self._model.device)

            outputs = self._model.generate(
                **inputs,
                max_new_tokens=256,
                do_sample=False,
                temperature=None,
                top_p=None,
            )

            generated_text = self._processor.decode(
                outputs[0],
                skip_special_tokens=False,
            )

            function_call = self._parse_function_call(generated_text)

            if function_call:
                logger.info(f'Parsed function call: {function_call}')
            else:
                logger.debug(
                    f'No function call found in output: {generated_text}'
                )

            return function_call

        except Exception as e:
            logger.error(f'Error during intent parsing: {e}')
            return None

    def _parse_function_call(self, output: str) -> Optional[Dict[str, Any]]:
        """Parse FunctionGemma output format into a structured dictionary.

        The FunctionGemma output format uses special tokens to delimit
        function calls:
        <start_function_call>call:func_name{arg1:<escape>value1<escape>,...}<end_function_call>

        Args:
            output: The raw text output from FunctionGemma.

        Returns:
            A dictionary with 'name' and 'args' keys if a valid function call
            is found, None otherwise.
        """
        start_tag = '<start_function_call>'
        end_tag = '<end_function_call>'

        start_idx = output.find(start_tag)
        end_idx = output.find(end_tag)

        if start_idx == -1 or end_idx == -1:
            logger.debug(f'No function call markers found in output')
            return None

        start_idx += len(start_tag)
        function_call_str = output[start_idx:end_idx]

        func_call_pattern = r'^call:(\w+)\{(.+)\}$'
        match = re.match(func_call_pattern, function_call_str)

        if not match:
            logger.debug(f'Invalid function call format: {function_call_str}')
            return None

        func_name = match.group(1)
        args_str = match.group(2)

        try:
            args = self._extract_args(args_str)
        except Exception as e:
            logger.error(f'Failed to extract arguments: {e}')
            return None

        return {'name': func_name, 'args': args}

    def _extract_args(self, args_str: str) -> Dict[str, Any]:
        """Extract arguments from the function call string.

        Parses argument strings in the format:
        arg1:<escape>value1<escape>,arg2:<escape>value2<escape>

        Args:
            args_str: The argument string to parse.

        Returns:
            A dictionary mapping argument names to their values.

        Raises:
            ValueError: If the argument string is malformed.
        """
        if not args_str.strip():
            return {}

        args: Dict[str, Any] = {}
        escape_token = '<escape>'

        while args_str:
            eq_idx = args_str.find(':')

            if eq_idx == -1:
                raise ValueError(f'Invalid argument format: {args_str}')

            arg_name = args_str[:eq_idx].strip()
            args_str = args_str[eq_idx + 1 :]

            if not args_str.startswith(escape_token):
                raise ValueError(
                    f"Expected escape token for argument '{arg_name}': {args_str}"
                )

            args_str = args_str[len(escape_token) :]
            end_escape_idx = args_str.find(escape_token)

            if end_escape_idx == -1:
                raise ValueError(
                    f"Missing closing escape token for argument '{arg_name}'"
                )

            arg_value = args_str[:end_escape_idx]
            args[arg_name] = arg_value
            args_str = args_str[end_escape_idx + len(escape_token) :]

            if args_str.startswith(','):
                args_str = args_str[1:].strip()

        return args
