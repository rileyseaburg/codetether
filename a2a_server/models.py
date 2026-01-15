"""
Pydantic models for A2A protocol data structures.

These models are based on the A2A specification and provide validation
and serialization for all protocol objects.
"""

from typing import Any, Dict, List, Optional, Union, Literal
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class AgentProvider(BaseModel):
    """Represents the service provider of an agent."""

    organization: str = Field(
        ..., description="The name of the agent provider's organization"
    )
    url: str = Field(
        ...,
        description="A URL for the agent provider's website or relevant documentation",
    )


class AgentExtension(BaseModel):
    """A declaration of a protocol extension supported by an Agent."""

    uri: str = Field(
        ..., description='The unique URI identifying the extension'
    )
    description: Optional[str] = Field(
        None,
        description='A human-readable description of how this agent uses the extension',
    )
    required: bool = Field(
        False,
        description="If true, the client must understand and comply with the extension's requirements",
    )


class LiveKitInterface(BaseModel):
    """Configuration for LiveKit media interface."""

    token_endpoint: str = Field(
        ..., description='Endpoint for obtaining LiveKit access tokens'
    )
    join_url_template: Optional[str] = Field(
        None, description='Template for generating join URLs'
    )
    server_managed: bool = Field(
        True, description='Whether the server manages LiveKit resources'
    )


class AdditionalInterfaces(BaseModel):
    """Additional interfaces supported by the agent beyond core A2A."""

    model_config = {'extra': 'allow'}

    livekit: Optional[LiveKitInterface] = Field(
        None, description='LiveKit real-time media interface configuration'
    )


class AgentCapabilities(BaseModel):
    """Defines optional capabilities supported by an agent."""

    streaming: Optional[bool] = Field(
        None,
        description='Indicates if the agent supports Server-Sent Events (SSE) for streaming responses',
    )
    push_notifications: Optional[bool] = Field(
        None,
        description='Indicates if the agent supports sending push notifications for asynchronous task updates',
    )
    state_transition_history: Optional[bool] = Field(
        None,
        description='Indicates if the agent provides a history of state transitions for a task',
    )
    media: Optional[bool] = Field(
        None,
        description='Indicates if the agent supports real-time media sessions',
    )
    extensions: Optional[List[AgentExtension]] = Field(
        None, description='A list of protocol extensions supported by the agent'
    )


class AgentSkill(BaseModel):
    """Describes a specific skill or capability that an agent can perform."""

    id: str = Field(
        ..., description='A unique identifier for the skill within the agent'
    )
    name: str = Field(..., description='A human-readable name for the skill')
    description: str = Field(
        ..., description='A detailed description of what the skill does'
    )
    input_modes: List[str] = Field(
        default_factory=list,
        description='List of supported input content types',
    )
    output_modes: List[str] = Field(
        default_factory=list,
        description='List of supported output content types',
    )
    examples: Optional[List[Dict[str, Any]]] = Field(
        None, description='Example inputs and outputs for the skill'
    )


class AuthenticationScheme(BaseModel):
    """Describes an authentication scheme required by the agent."""

    scheme: str = Field(
        ...,
        description="The authentication scheme (e.g., 'Bearer', 'Basic', 'OAuth2')",
    )
    description: Optional[str] = Field(
        None,
        description='Human-readable description of the authentication requirements',
    )


class AgentCard(BaseModel):
    """The Agent Card is the core discovery document for an A2A agent."""

    name: str = Field(..., description='A human-readable name for the agent')
    description: str = Field(
        ..., description="A description of the agent's purpose and capabilities"
    )
    url: str = Field(
        ..., description='The base URL where the A2A server can be reached'
    )
    provider: AgentProvider = Field(
        ...,
        description='Information about the organization providing this agent',
    )
    capabilities: Optional[AgentCapabilities] = Field(
        None, description='Optional capabilities supported by the agent'
    )
    authentication: List[AuthenticationScheme] = Field(
        default_factory=list,
        description='Authentication schemes required to interact with the agent',
    )
    skills: List[AgentSkill] = Field(
        default_factory=list, description='List of skills the agent can perform'
    )
    additional_interfaces: Optional[AdditionalInterfaces] = Field(
        None, description='Additional interfaces supported beyond core A2A'
    )
    version: str = Field('1.0', description='Version of the agent card format')


class TaskStatus(str, Enum):
    """
    Enumeration of possible task statuses.

    Aligned with the A2A protocol specification:
    - submitted: Task created and acknowledged
    - working: Actively processing
    - completed: Finished successfully (TERMINAL)
    - failed: Done but failed (TERMINAL)
    - cancelled: Cancelled before completion (TERMINAL)
    - input-required: Awaiting additional input
    - rejected: Agent declined the task (TERMINAL)
    - auth-required: Needs out-of-band authentication

    Note: PENDING is deprecated and maps to SUBMITTED for backwards compatibility.
    """

    # A2A Protocol States
    SUBMITTED = 'submitted'
    WORKING = 'working'
    INPUT_REQUIRED = 'input-required'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'
    FAILED = 'failed'
    REJECTED = 'rejected'
    AUTH_REQUIRED = 'auth-required'

    # Legacy alias - maps to SUBMITTED for backwards compatibility
    PENDING = 'pending'

    @classmethod
    def from_string(cls, value: str) -> 'TaskStatus':
        """
        Convert a string to TaskStatus, handling legacy 'pending' value.

        Args:
            value: String representation of the status

        Returns:
            TaskStatus enum value

        Raises:
            ValueError: If the value is not a valid status
        """
        # Normalize to lowercase
        normalized = value.lower().strip()

        # Handle legacy 'pending' -> 'submitted' mapping
        if normalized == 'pending':
            return cls.SUBMITTED

        try:
            return cls(normalized)
        except ValueError:
            raise ValueError(
                f"Invalid task status: '{value}'. "
                f'Valid values: {[s.value for s in cls]}'
            )

    def is_terminal(self) -> bool:
        """Check if this status is a terminal state."""
        return self in _TERMINAL_STATUSES

    def is_active(self) -> bool:
        """Check if this status is an active (non-terminal) state."""
        return self not in _TERMINAL_STATUSES


# Terminal states - tasks in these states cannot transition further
_TERMINAL_STATUSES = {
    TaskStatus.COMPLETED,
    TaskStatus.FAILED,
    TaskStatus.CANCELLED,
    TaskStatus.REJECTED,
}


class Task(BaseModel):
    """Represents a stateful unit of work being processed by an A2A Server for an A2A Client."""

    id: str = Field(..., description='A unique identifier for the task')
    status: TaskStatus = Field(
        ..., description='The current status of the task'
    )
    created_at: datetime = Field(..., description='When the task was created')
    updated_at: datetime = Field(
        ..., description='When the task was last updated'
    )
    title: Optional[str] = Field(
        None, description='A human-readable title for the task'
    )
    description: Optional[str] = Field(
        None, description='A description of what the task is doing'
    )
    progress: Optional[float] = Field(
        None, ge=0.0, le=1.0, description='Progress percentage (0.0 to 1.0)'
    )
    messages: Optional[List['Message']] = Field(
        None, description='Messages exchanged during the task'
    )
    worker_id: Optional[str] = Field(
        None, description='ID of the worker that claimed this task'
    )
    claimed_at: Optional[datetime] = Field(
        None, description='When the task was claimed by a worker'
    )


class Part(BaseModel):
    """A component of a message that can contain text, files, or structured data."""

    type: str = Field(
        ..., description="The type of content (e.g., 'text', 'file', 'data')"
    )
    content: Any = Field(..., description='The actual content of the part')
    metadata: Optional[Dict[str, Any]] = Field(
        None, description='Additional metadata for the part'
    )


class Message(BaseModel):
    """A message exchanged between agents."""

    parts: List[Part] = Field(..., description='List of message parts')
    metadata: Optional[Dict[str, Any]] = Field(
        None, description='Additional message metadata'
    )


class JSONRPCRequest(BaseModel):
    """JSON-RPC 2.0 request structure."""

    jsonrpc: Literal['2.0'] = Field('2.0', description='JSON-RPC version')
    method: str = Field(..., description='The name of the method to be invoked')
    params: Optional[Dict[str, Any]] = Field(
        None, description='Parameters for the method'
    )
    id: Optional[Union[str, int]] = Field(
        None, description='Unique identifier for the request'
    )


class JSONRPCResponse(BaseModel):
    """JSON-RPC 2.0 response structure."""

    jsonrpc: Literal['2.0'] = Field('2.0', description='JSON-RPC version')
    id: Optional[Union[str, int]] = Field(
        None, description='Identifier matching the request'
    )
    result: Optional[Any] = Field(
        None, description='The result of the method call'
    )
    error: Optional[Dict[str, Any]] = Field(
        None, description='Error information if the call failed'
    )


class JSONRPCError(BaseModel):
    """JSON-RPC 2.0 error structure."""

    code: int = Field(..., description='A number that indicates the error type')
    message: str = Field(..., description='A short description of the error')
    data: Optional[Any] = Field(
        None, description='Additional information about the error'
    )


# Method-specific request/response models
class SendMessageRequest(BaseModel):
    """Request to send a message to an agent."""

    message: Message = Field(..., description='The message to send')
    task_id: Optional[str] = Field(
        None, description='Optional task ID to associate with the message'
    )
    skill_id: Optional[str] = Field(
        None, description='Optional skill ID to use for processing'
    )


class SendMessageResponse(BaseModel):
    """Response from sending a message."""

    task: Task = Field(
        ..., description='The task created or updated by the message'
    )
    message: Optional[Message] = Field(
        None, description='Optional response message'
    )


class GetTaskRequest(BaseModel):
    """Request to get information about a task."""

    task_id: str = Field(..., description='The ID of the task to retrieve')


class GetTaskResponse(BaseModel):
    """Response containing task information."""

    task: Task = Field(..., description='The requested task')


class CancelTaskRequest(BaseModel):
    """Request to cancel a task."""

    task_id: str = Field(..., description='The ID of the task to cancel')


class CancelTaskResponse(BaseModel):
    """Response confirming task cancellation."""

    task: Task = Field(..., description='The cancelled task')


class StreamMessageRequest(BaseModel):
    """Request to stream a message with real-time updates."""

    message: Message = Field(..., description='The message to send')
    task_id: Optional[str] = Field(
        None, description='Optional task ID to associate with the message'
    )
    skill_id: Optional[str] = Field(
        None, description='Optional skill ID to use for processing'
    )


class TaskStatusUpdateEvent(BaseModel):
    """Event indicating a change in task status."""

    task: Task = Field(..., description='The updated task')
    message: Optional[Message] = Field(
        None, description='Optional message associated with the update'
    )
    final: bool = Field(
        False, description='Whether this is the final update for the task'
    )


class StreamingMessageResponse(BaseModel):
    """Response for streaming message operations."""

    event: TaskStatusUpdateEvent = Field(
        ..., description='The task status update event'
    )


# Media-specific request/response models
class MediaRequestRequest(BaseModel):
    """Request to create or join a media session."""

    room_name: Optional[str] = Field(
        None,
        description='Specific room name to create/join (auto-generated if not provided)',
    )
    participant_identity: str = Field(
        ..., description='Identity of the participant'
    )
    role: str = Field(
        'participant',
        description='Role for the participant (admin, moderator, publisher, participant, viewer)',
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None, description='Optional metadata for the room or participant'
    )
    max_participants: int = Field(
        50,
        description='Maximum number of participants (only used when creating new rooms)',
    )


class MediaRequestResponse(BaseModel):
    """Response containing media session information."""

    task: Task = Field(..., description='The task managing this media session')
    room_name: str = Field(..., description='Name of the LiveKit room')
    room_sid: Optional[str] = Field(None, description='LiveKit room SID')
    join_url: str = Field(..., description='URL to join the media session')
    access_token: str = Field(..., description='LiveKit access token')
    participant_identity: str = Field(
        ..., description='Identity of the participant'
    )
    expires_at: datetime = Field(
        ..., description='When the access token expires'
    )


class MediaJoinRequest(BaseModel):
    """Request to join an existing media session."""

    room_name: str = Field(..., description='Name of the room to join')
    participant_identity: str = Field(
        ..., description='Identity of the participant'
    )
    role: str = Field('participant', description='Role for the participant')
    metadata: Optional[str] = Field(
        None, description='Optional metadata for the participant'
    )


class MediaJoinResponse(BaseModel):
    """Response for joining a media session."""

    join_url: str = Field(..., description='URL to join the media session')
    access_token: str = Field(..., description='LiveKit access token')
    participant_identity: str = Field(
        ..., description='Identity of the participant'
    )
    expires_at: datetime = Field(
        ..., description='When the access token expires'
    )


class LiveKitTokenRequest(BaseModel):
    """Request for a LiveKit access token."""

    room_name: str = Field(..., description='Name of the room')
    identity: str = Field(..., description='Identity of the participant')
    role: str = Field('participant', description='Role for the participant')
    metadata: Optional[str] = Field(
        None, description='Optional metadata for the participant'
    )
    ttl_minutes: int = Field(
        60, ge=1, le=1440, description='Token time-to-live in minutes (1-1440)'
    )


class LiveKitTokenResponse(BaseModel):
    """Response containing LiveKit access token."""

    access_token: str = Field(..., description='LiveKit JWT access token')
    join_url: str = Field(..., description='URL to join the media session')
    expires_at: datetime = Field(
        ..., description='When the access token expires'
    )


# Rebuild Task model to resolve forward reference to Message
Task.model_rebuild()
