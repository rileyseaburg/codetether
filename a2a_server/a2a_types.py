"""
A2A Protocol State Types and Mappings

This module provides alignment between our internal task states and the
official A2A protocol task states as defined in the specification.

A2A Spec States:
- submitted: Task created and acknowledged
- working: Actively processing
- completed: Finished successfully (TERMINAL)
- failed: Done but failed (TERMINAL)
- cancelled: Cancelled before completion (TERMINAL)
- input-required: Awaiting additional input
- rejected: Agent declined the task (TERMINAL)
- auth-required: Needs out-of-band authentication

Our Internal States (TaskStatus):
- SUBMITTED: Initial state after creation
- PENDING: Legacy alias for submitted (deprecated)
- WORKING: Actively processing
- INPUT_REQUIRED: Awaiting user input
- COMPLETED: Finished successfully (TERMINAL)
- FAILED: Failed (TERMINAL)
- CANCELLED: Cancelled (TERMINAL)
- REJECTED: Agent declined (TERMINAL)
- AUTH_REQUIRED: Needs authentication
"""

from enum import Enum
from typing import Set


class A2ATaskState(str, Enum):
    """
    Official A2A protocol task states.

    These are the states defined in the A2A specification that should be
    used when communicating with external A2A clients and servers.
    """

    SUBMITTED = 'submitted'
    WORKING = 'working'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'
    INPUT_REQUIRED = 'input-required'
    REJECTED = 'rejected'
    AUTH_REQUIRED = 'auth-required'


# Terminal states - once a task reaches these, it cannot transition further
A2A_TERMINAL_STATES: Set[A2ATaskState] = {
    A2ATaskState.COMPLETED,
    A2ATaskState.FAILED,
    A2ATaskState.CANCELLED,
    A2ATaskState.REJECTED,
}

# Non-terminal states - task can still transition
A2A_ACTIVE_STATES: Set[A2ATaskState] = {
    A2ATaskState.SUBMITTED,
    A2ATaskState.WORKING,
    A2ATaskState.INPUT_REQUIRED,
    A2ATaskState.AUTH_REQUIRED,
}


def is_a2a_terminal_state(state: A2ATaskState) -> bool:
    """
    Check if an A2A state is terminal.

    Terminal states indicate the task has reached a final state and
    cannot transition to any other state.

    Args:
        state: The A2A task state to check

    Returns:
        True if the state is terminal, False otherwise
    """
    return state in A2A_TERMINAL_STATES


def is_a2a_active_state(state: A2ATaskState) -> bool:
    """
    Check if an A2A state is active (non-terminal).

    Active states indicate the task is still in progress and can
    transition to other states.

    Args:
        state: The A2A task state to check

    Returns:
        True if the state is active, False otherwise
    """
    return state in A2A_ACTIVE_STATES


# Import here to avoid circular imports - we need the actual TaskStatus
# This will be populated after models.py is updated
def _get_task_status():
    """Lazy import of TaskStatus to avoid circular imports."""
    from a2a_server.models import TaskStatus

    return TaskStatus


# Mapping from internal TaskStatus to A2A protocol states
_INTERNAL_TO_A2A_MAP = {
    'submitted': A2ATaskState.SUBMITTED,
    'pending': A2ATaskState.SUBMITTED,  # Legacy mapping
    'working': A2ATaskState.WORKING,
    'input-required': A2ATaskState.INPUT_REQUIRED,
    'completed': A2ATaskState.COMPLETED,
    'failed': A2ATaskState.FAILED,
    'cancelled': A2ATaskState.CANCELLED,
    'rejected': A2ATaskState.REJECTED,
    'auth-required': A2ATaskState.AUTH_REQUIRED,
}

# Mapping from A2A protocol states to internal TaskStatus values
_A2A_TO_INTERNAL_MAP = {
    A2ATaskState.SUBMITTED: 'submitted',
    A2ATaskState.WORKING: 'working',
    A2ATaskState.INPUT_REQUIRED: 'input-required',
    A2ATaskState.COMPLETED: 'completed',
    A2ATaskState.FAILED: 'failed',
    A2ATaskState.CANCELLED: 'cancelled',
    A2ATaskState.REJECTED: 'rejected',
    A2ATaskState.AUTH_REQUIRED: 'auth-required',
}


def internal_to_a2a_state(internal_state) -> A2ATaskState:
    """
    Convert an internal TaskStatus to the corresponding A2A protocol state.

    Args:
        internal_state: TaskStatus enum value or string representation

    Returns:
        The corresponding A2ATaskState

    Raises:
        ValueError: If the internal state has no A2A mapping

    Examples:
        >>> internal_to_a2a_state(TaskStatus.PENDING)
        <A2ATaskState.SUBMITTED: 'submitted'>

        >>> internal_to_a2a_state(TaskStatus.WORKING)
        <A2ATaskState.WORKING: 'working'>

        >>> internal_to_a2a_state('completed')
        <A2ATaskState.COMPLETED: 'completed'>
    """
    # Handle both enum and string values
    if hasattr(internal_state, 'value'):
        state_value = internal_state.value
    else:
        state_value = str(internal_state).lower()

    if state_value not in _INTERNAL_TO_A2A_MAP:
        raise ValueError(
            f"Unknown internal state '{state_value}'. "
            f'Valid states: {list(_INTERNAL_TO_A2A_MAP.keys())}'
        )

    return _INTERNAL_TO_A2A_MAP[state_value]


def a2a_to_internal_state(a2a_state: A2ATaskState):
    """
    Convert an A2A protocol state to the corresponding internal TaskStatus.

    Args:
        a2a_state: A2ATaskState enum value or string representation

    Returns:
        The corresponding TaskStatus enum value

    Raises:
        ValueError: If the A2A state has no internal mapping

    Examples:
        >>> a2a_to_internal_state(A2ATaskState.SUBMITTED)
        <TaskStatus.SUBMITTED: 'submitted'>

        >>> a2a_to_internal_state('working')
        <TaskStatus.WORKING: 'working'>
    """
    TaskStatus = _get_task_status()

    # Handle both enum and string values
    if isinstance(a2a_state, str):
        try:
            a2a_state = A2ATaskState(a2a_state)
        except ValueError:
            raise ValueError(
                f"Unknown A2A state '{a2a_state}'. "
                f'Valid states: {[s.value for s in A2ATaskState]}'
            )

    if a2a_state not in _A2A_TO_INTERNAL_MAP:
        raise ValueError(
            f"Unknown A2A state '{a2a_state}'. "
            f'Valid states: {list(_A2A_TO_INTERNAL_MAP.keys())}'
        )

    internal_value = _A2A_TO_INTERNAL_MAP[a2a_state]
    return TaskStatus(internal_value)


def is_internal_terminal_state(internal_state) -> bool:
    """
    Check if an internal TaskStatus is terminal.

    Args:
        internal_state: TaskStatus enum value or string representation

    Returns:
        True if the state is terminal, False otherwise

    Examples:
        >>> is_internal_terminal_state(TaskStatus.COMPLETED)
        True

        >>> is_internal_terminal_state(TaskStatus.WORKING)
        False
    """
    try:
        a2a_state = internal_to_a2a_state(internal_state)
        return is_a2a_terminal_state(a2a_state)
    except ValueError:
        return False


def is_internal_active_state(internal_state) -> bool:
    """
    Check if an internal TaskStatus is active (non-terminal).

    Args:
        internal_state: TaskStatus enum value or string representation

    Returns:
        True if the state is active, False otherwise
    """
    try:
        a2a_state = internal_to_a2a_state(internal_state)
        return is_a2a_active_state(a2a_state)
    except ValueError:
        return False


# Valid state transitions as defined by A2A protocol
# Key is the current state, value is set of valid next states
VALID_STATE_TRANSITIONS = {
    A2ATaskState.SUBMITTED: {
        A2ATaskState.WORKING,
        A2ATaskState.COMPLETED,
        A2ATaskState.FAILED,
        A2ATaskState.CANCELLED,
        A2ATaskState.REJECTED,
        A2ATaskState.INPUT_REQUIRED,
        A2ATaskState.AUTH_REQUIRED,
    },
    A2ATaskState.WORKING: {
        A2ATaskState.COMPLETED,
        A2ATaskState.FAILED,
        A2ATaskState.CANCELLED,
        A2ATaskState.INPUT_REQUIRED,
        A2ATaskState.AUTH_REQUIRED,
    },
    A2ATaskState.INPUT_REQUIRED: {
        A2ATaskState.WORKING,
        A2ATaskState.COMPLETED,
        A2ATaskState.FAILED,
        A2ATaskState.CANCELLED,
    },
    A2ATaskState.AUTH_REQUIRED: {
        A2ATaskState.WORKING,
        A2ATaskState.COMPLETED,
        A2ATaskState.FAILED,
        A2ATaskState.CANCELLED,
    },
    # Terminal states cannot transition
    A2ATaskState.COMPLETED: set(),
    A2ATaskState.FAILED: set(),
    A2ATaskState.CANCELLED: set(),
    A2ATaskState.REJECTED: set(),
}


def is_valid_transition(
    from_state: A2ATaskState, to_state: A2ATaskState
) -> bool:
    """
    Check if a state transition is valid according to A2A protocol.

    Args:
        from_state: Current state
        to_state: Target state

    Returns:
        True if the transition is valid, False otherwise

    Examples:
        >>> is_valid_transition(A2ATaskState.SUBMITTED, A2ATaskState.WORKING)
        True

        >>> is_valid_transition(A2ATaskState.COMPLETED, A2ATaskState.WORKING)
        False
    """
    if from_state not in VALID_STATE_TRANSITIONS:
        return False
    return to_state in VALID_STATE_TRANSITIONS[from_state]


def get_valid_next_states(current_state: A2ATaskState) -> Set[A2ATaskState]:
    """
    Get the set of valid states that can be transitioned to from the current state.

    Args:
        current_state: The current A2A task state

    Returns:
        Set of valid next states (empty set for terminal states)

    Examples:
        >>> get_valid_next_states(A2ATaskState.WORKING)
        {<A2ATaskState.COMPLETED>, <A2ATaskState.FAILED>, ...}

        >>> get_valid_next_states(A2ATaskState.COMPLETED)
        set()
    """
    return VALID_STATE_TRANSITIONS.get(current_state, set())


# Convenience constants for commonly used state sets
TERMINAL_STATES = A2A_TERMINAL_STATES
ACTIVE_STATES = A2A_ACTIVE_STATES
WAITING_STATES = {A2ATaskState.INPUT_REQUIRED, A2ATaskState.AUTH_REQUIRED}
PROCESSING_STATES = {A2ATaskState.SUBMITTED, A2ATaskState.WORKING}
