"""
Pydantic models for A2A protocol data structures.

These models provide full parity with the A2A gRPC specification (a2a.proto)
and the Rust codetether-agent types.rs canonical wire format.  All spec-facing
types use camelCase JSON serialization via Pydantic aliases to match the Rust
agent's ``#[serde(rename_all = "camelCase")]`` output.

Backwards compatibility: existing code that imports TaskStatus, Task, Message,
Part, etc. continues to work.  Internal-only fields on Task (created_at,
worker_id, …) are preserved but excluded from spec JSON via ``a2a_dict()``.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, model_validator


# ═══════════════════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════════════════


class TaskState(str, Enum):
    """A2A task states — kebab-case to match Rust ``#[serde(rename_all = "kebab-case")]``."""

    SUBMITTED = 'submitted'
    WORKING = 'working'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'
    INPUT_REQUIRED = 'input-required'
    REJECTED = 'rejected'
    AUTH_REQUIRED = 'auth-required'

    def is_terminal(self) -> bool:
        return self in _TERMINAL_STATES

    def is_active(self) -> bool:
        return not self.is_terminal()


_TERMINAL_STATES = {
    TaskState.COMPLETED,
    TaskState.FAILED,
    TaskState.CANCELLED,
    TaskState.REJECTED,
}


class Role(str, Enum):
    """Message role — lowercase to match Rust ``MessageRole``."""

    USER = 'user'
    AGENT = 'agent'


class TaskStatus(str, Enum):
    """
    Task status values — kept for backwards compatibility.

    Prefer ``TaskState`` for new code.

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
        """Convert a string to TaskStatus, handling legacy 'pending' value."""
        normalized = value.lower().strip()
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

    def to_task_state(self) -> TaskState:
        """Convert to the canonical TaskState enum."""
        val = self.value
        if val == 'pending':
            val = 'submitted'
        return TaskState(val)


# Terminal states - tasks in these states cannot transition further
_TERMINAL_STATUSES = {
    TaskStatus.COMPLETED,
    TaskStatus.FAILED,
    TaskStatus.CANCELLED,
    TaskStatus.REJECTED,
}


# ═══════════════════════════════════════════════════════════════════════════
# Part types — tagged union on ``kind`` matching Rust types.rs
# ═══════════════════════════════════════════════════════════════════════════


class FileContent(BaseModel):
    """File payload — bytes (base64) or URI."""

    model_config = {'populate_by_name': True}

    bytes: Optional[str] = Field(None, description='Base64 encoded file bytes')
    uri: Optional[str] = Field(None, description='URI to the file')
    mime_type: Optional[str] = Field(None, alias='mimeType')
    name: Optional[str] = None


class Part(BaseModel):
    """
    A section of communication content.

    Spec wire format: ``{"kind": "text", "text": "..."}``
    Legacy format:    ``{"type": "text", "content": "..."}``

    Both formats are accepted on input; spec format is always emitted.
    """

    model_config = {'populate_by_name': True}

    kind: str = Field('text', description='Discriminator: text | file | data')
    text: Optional[str] = None
    file: Optional[FileContent] = None
    data: Optional[Any] = None
    metadata: Optional[Dict[str, Any]] = None

    # Legacy compat fields — not serialized in spec output
    type: Optional[str] = Field(None, exclude=True)
    content: Optional[Any] = Field(None, exclude=True)

    @model_validator(mode='before')
    @classmethod
    def _accept_legacy_format(cls, values: Any) -> Any:
        """Accept legacy ``{"type": "text", "content": "hello"}`` and convert."""
        if isinstance(values, dict):
            if 'kind' in values:
                return values
            t = values.get('type')
            c = values.get('content')
            if t and c is not None and 'kind' not in values:
                if t == 'text':
                    return {'kind': 'text', 'text': str(c), 'metadata': values.get('metadata')}
                elif t == 'file':
                    if isinstance(c, dict):
                        return {'kind': 'file', 'file': c, 'metadata': values.get('metadata')}
                    return {'kind': 'file', 'file': {'uri': str(c)}, 'metadata': values.get('metadata')}
                elif t == 'data':
                    return {'kind': 'data', 'data': c, 'metadata': values.get('metadata')}
                else:
                    return {'kind': t, 'text': str(c), 'metadata': values.get('metadata')}
        return values


# ═══════════════════════════════════════════════════════════════════════════
# Message — full spec fields
# ═══════════════════════════════════════════════════════════════════════════


class Message(BaseModel):
    """An A2A protocol message."""

    model_config = {'populate_by_name': True}

    message_id: str = Field(default='', alias='messageId')
    role: Role = Field(default=Role.USER)
    parts: List[Part] = Field(default_factory=list)
    context_id: Optional[str] = Field(None, alias='contextId')
    task_id: Optional[str] = Field(None, alias='taskId')
    metadata: Optional[Dict[str, Any]] = None
    extensions: List[str] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════
# Artifact
# ═══════════════════════════════════════════════════════════════════════════


class Artifact(BaseModel):
    """Output artifact produced by a task."""

    model_config = {'populate_by_name': True}

    artifact_id: str = Field(..., alias='artifactId')
    parts: List[Part] = Field(default_factory=list)
    name: Optional[str] = None
    description: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    extensions: List[str] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════
# TaskStatusInfo — the proto ``TaskStatus`` message (state + message + ts)
# Named TaskStatusInfo to avoid collision with the TaskStatus enum.
# ═══════════════════════════════════════════════════════════════════════════


class TaskStatusInfo(BaseModel):
    """Structured task status (state + optional message + timestamp)."""

    state: TaskState = Field(...)
    message: Optional[Message] = None
    timestamp: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════
# Task — spec-aligned fields + internal operational fields
# ═══════════════════════════════════════════════════════════════════════════


class Task(BaseModel):
    """
    A2A Task — the core unit of work.

    Spec fields:  id, context_id, status, artifacts, history, metadata
    Internal fields: created_at, updated_at, title, description, progress,
                     messages, worker_id, claimed_at, model_ref, …
    """

    model_config = {'populate_by_name': True}

    id: str = Field(..., description='A unique identifier for the task')
    context_id: Optional[str] = Field(None, alias='contextId')
    status: TaskStatus = Field(
        ..., description='The current status of the task'
    )

    # Spec fields
    artifacts: List[Artifact] = Field(default_factory=list)
    history: List[Message] = Field(default_factory=list)
    task_metadata: Dict[str, Any] = Field(default_factory=dict, alias='metadata')

    # Internal operational fields (not in proto spec)
    created_at: datetime = Field(default_factory=datetime.utcnow,
                                 description='When the task was created')
    updated_at: datetime = Field(default_factory=datetime.utcnow,
                                 description='When the task was last updated')
    title: Optional[str] = Field(
        None, description='A human-readable title for the task'
    )
    description: Optional[str] = Field(
        None, description='A description of what the task is doing'
    )
    progress: Optional[float] = Field(
        None, ge=0.0, le=1.0, description='Progress percentage (0.0 to 1.0)'
    )
    messages: Optional[List[Message]] = Field(
        None, description='Messages exchanged during the task (legacy, prefer history)'
    )
    worker_id: Optional[str] = Field(
        None, description='ID of the worker that claimed this task'
    )
    claimed_at: Optional[datetime] = Field(
        None, description='When the task was claimed by a worker'
    )

    # Model reference fields
    model_ref: Optional[str] = Field(
        None,
        description='Normalized model reference (provider:model) for the controller model',
    )
    subcall_model_ref: Optional[str] = Field(
        None,
        description='Optional override for subcall model in RLM tasks (provider:model)',
    )

    # Resolved subcall model fields (set by A2A during dispatch)
    resolved_subcall_model_ref: Optional[str] = Field(
        None,
        description='Resolved subcall model reference for RLM execution',
    )
    resolved_subcall_source: Optional[str] = Field(
        None,
        description='Source of subcall model resolution: task, config, fallback, or controller',
    )
    resolved_subcall_warning: Optional[str] = Field(
        None,
        description='Warning message if using controller fallback for subcalls',
    )

    def a2a_dict(self) -> Dict[str, Any]:
        """Serialize to spec-compatible JSON (camelCase, only spec fields)."""
        return {
            'id': self.id,
            'contextId': self.context_id,
            'status': {
                'state': self.status.to_task_state().value
                if isinstance(self.status, TaskStatus)
                else self.status.value,
                'timestamp': self.updated_at.isoformat() + 'Z' if self.updated_at else None,
            },
            'artifacts': [a.model_dump(by_alias=True, exclude_none=True) for a in self.artifacts],
            'history': [m.model_dump(by_alias=True, exclude_none=True) for m in self.history],
            'metadata': self.task_metadata,
        }


# ═══════════════════════════════════════════════════════════════════════════
# Push notification types
# ═══════════════════════════════════════════════════════════════════════════


class AuthenticationInfo(BaseModel):
    """Authentication details for push notifications."""

    schemes: List[str] = Field(default_factory=list)
    credentials: Optional[str] = None


class PushNotificationConfig(BaseModel):
    """Configuration for push notifications."""

    model_config = {'populate_by_name': True}

    url: str = Field(...)
    token: Optional[str] = None
    id: Optional[str] = None
    authentication: Optional[AuthenticationInfo] = None


class TaskPushNotificationConfig(BaseModel):
    """A push notification config bound to a task."""

    model_config = {'populate_by_name': True}

    id: str = Field(..., description='Task ID')
    push_notification_config: PushNotificationConfig = Field(
        ..., alias='pushNotificationConfig'
    )


# ═══════════════════════════════════════════════════════════════════════════
# Send configuration
# ═══════════════════════════════════════════════════════════════════════════


class SendMessageConfiguration(BaseModel):
    """Configuration for a message/send request."""

    model_config = {'populate_by_name': True}

    accepted_output_modes: List[str] = Field(
        default_factory=list, alias='acceptedOutputModes'
    )
    blocking: Optional[bool] = None
    history_length: Optional[int] = Field(None, alias='historyLength')
    push_notification_config: Optional[PushNotificationConfig] = Field(
        None, alias='pushNotificationConfig'
    )


# ═══════════════════════════════════════════════════════════════════════════
# Streaming / event types
# ═══════════════════════════════════════════════════════════════════════════


class TaskStatusUpdateEvent(BaseModel):
    """SSE event: task status changed.

    Spec format: ``{id, status: {state, message, timestamp}, final, metadata}``
    Legacy format: ``{task: Task, message: Message, final: bool}``

    Both are accepted; spec format is emitted.
    """

    model_config = {'populate_by_name': True}

    id: str = Field(...)
    status: TaskStatusInfo = Field(...)
    final: bool = Field(False)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    # Legacy compat fields — accepted on input only
    task: Optional[Any] = Field(None, exclude=True)
    message: Optional[Any] = Field(None, exclude=True)

    @model_validator(mode='before')
    @classmethod
    def _accept_legacy(cls, values: Any) -> Any:
        if isinstance(values, dict):
            if 'task' in values and 'id' not in values:
                t = values['task']
                if hasattr(t, 'id'):
                    state_val = (
                        t.status.to_task_state().value
                        if hasattr(t.status, 'to_task_state')
                        else (t.status.value if hasattr(t.status, 'value') else str(t.status))
                    )
                    return {
                        'id': t.id,
                        'status': {'state': state_val},
                        'final': values.get('final', False),
                        'metadata': {},
                    }
                elif isinstance(t, dict):
                    task_status = t.get('status', 'submitted')
                    if isinstance(task_status, str):
                        state_val = task_status
                    elif hasattr(task_status, 'value'):
                        state_val = task_status.value
                    else:
                        state_val = str(task_status)
                    if state_val == 'pending':
                        state_val = 'submitted'
                    return {
                        'id': t.get('id', ''),
                        'status': {'state': state_val},
                        'final': values.get('final', False),
                        'metadata': {},
                    }
        return values


class TaskArtifactUpdateEvent(BaseModel):
    """SSE event: new artifact for a task."""

    model_config = {'populate_by_name': True}

    id: str = Field(...)
    artifact: Artifact = Field(...)
    append: bool = False
    last_chunk: bool = Field(False, alias='lastChunk')
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════════
# Security types — matching Rust SecurityScheme tagged union
# ═══════════════════════════════════════════════════════════════════════════


class APIKeySecurityScheme(BaseModel):
    """API key security scheme."""

    model_config = {'populate_by_name': True}

    type: Literal['apiKey'] = 'apiKey'
    description: Optional[str] = None
    name: str = Field(...)
    location: str = Field(..., alias='in')


class HTTPAuthSecurityScheme(BaseModel):
    """HTTP authentication security scheme (Bearer, Basic, etc.)."""

    model_config = {'populate_by_name': True}

    type: Literal['http'] = 'http'
    description: Optional[str] = None
    scheme: str = Field(...)
    bearer_format: Optional[str] = Field(None, alias='bearerFormat')


class OAuthFlowImplicit(BaseModel):
    """OAuth2 implicit flow."""

    model_config = {'populate_by_name': True}

    authorization_url: str = Field(..., alias='authorizationUrl')
    refresh_url: Optional[str] = Field(None, alias='refreshUrl')
    scopes: Dict[str, str] = Field(default_factory=dict)


class OAuthFlowAuthorizationCode(BaseModel):
    """OAuth2 authorization code flow."""

    model_config = {'populate_by_name': True}

    authorization_url: str = Field(..., alias='authorizationUrl')
    token_url: str = Field(..., alias='tokenUrl')
    refresh_url: Optional[str] = Field(None, alias='refreshUrl')
    scopes: Dict[str, str] = Field(default_factory=dict)


class OAuthFlowClientCredentials(BaseModel):
    """OAuth2 client credentials flow."""

    model_config = {'populate_by_name': True}

    token_url: str = Field(..., alias='tokenUrl')
    refresh_url: Optional[str] = Field(None, alias='refreshUrl')
    scopes: Dict[str, str] = Field(default_factory=dict)


class OAuthFlowDeviceCode(BaseModel):
    """OAuth2 device code flow."""

    model_config = {'populate_by_name': True}

    device_authorization_url: str = Field(..., alias='deviceAuthorizationUrl')
    token_url: str = Field(..., alias='tokenUrl')
    refresh_url: Optional[str] = Field(None, alias='refreshUrl')
    scopes: Dict[str, str] = Field(default_factory=dict)


class OAuthFlows(BaseModel):
    """Collection of OAuth2 flows."""

    model_config = {'populate_by_name': True}

    implicit: Optional[OAuthFlowImplicit] = None
    authorization_code: Optional[OAuthFlowAuthorizationCode] = Field(
        None, alias='authorizationCode'
    )
    client_credentials: Optional[OAuthFlowClientCredentials] = Field(
        None, alias='clientCredentials'
    )
    device_code: Optional[OAuthFlowDeviceCode] = Field(
        None, alias='deviceCode'
    )


class OAuth2SecurityScheme(BaseModel):
    """OAuth2 security scheme."""

    model_config = {'populate_by_name': True}

    type: Literal['oauth2'] = 'oauth2'
    description: Optional[str] = None
    flows: OAuthFlows = Field(default_factory=OAuthFlows)
    oauth2_metadata_url: Optional[str] = Field(None, alias='oauth2MetadataUrl')


class OpenIdConnectSecurityScheme(BaseModel):
    """OpenID Connect security scheme."""

    model_config = {'populate_by_name': True}

    type: Literal['openIdConnect'] = 'openIdConnect'
    description: Optional[str] = None
    open_id_connect_url: str = Field(..., alias='openIdConnectUrl')


class MutualTlsSecurityScheme(BaseModel):
    """Mutual TLS security scheme."""

    type: Literal['mutualTLS'] = 'mutualTLS'
    description: Optional[str] = None


# Discriminated union of all security schemes
SecurityScheme = Union[
    APIKeySecurityScheme,
    HTTPAuthSecurityScheme,
    OAuth2SecurityScheme,
    OpenIdConnectSecurityScheme,
    MutualTlsSecurityScheme,
]

# SecurityRequirement: name → list of required scope strings
SecurityRequirement = Dict[str, List[str]]


# ═══════════════════════════════════════════════════════════════════════════
# Agent card extension types
# ═══════════════════════════════════════════════════════════════════════════


class AgentExtension(BaseModel):
    """A protocol extension supported by an Agent."""

    uri: str = Field(...)
    description: Optional[str] = None
    required: bool = False
    params: Optional[Dict[str, Any]] = None


class AgentCardSignature(BaseModel):
    """JWS signature for an agent card."""

    model_config = {'populate_by_name': True}

    signature: str = Field(...)
    algorithm: Optional[str] = None
    key_id: Optional[str] = Field(None, alias='keyId')


class AgentInterface(BaseModel):
    """An additional transport interface."""

    model_config = {'populate_by_name': True}

    transport: str = Field(...)
    url: str = Field(...)
    content_types: List[str] = Field(default_factory=list, alias='contentTypes')


# ═══════════════════════════════════════════════════════════════════════════
# Agent card core types
# ═══════════════════════════════════════════════════════════════════════════


class AgentProvider(BaseModel):
    """Service provider of an agent."""

    organization: str = Field(...)
    url: str = Field(...)


class AgentCapabilities(BaseModel):
    """Capabilities advertised by an agent."""

    model_config = {'populate_by_name': True}

    streaming: bool = False
    push_notifications: bool = Field(False, alias='pushNotifications')
    state_transition_history: bool = Field(False, alias='stateTransitionHistory')
    extensions: Optional[List[AgentExtension]] = Field(default_factory=list)

    # Legacy field kept for backwards compat (not in proto spec)
    media: Optional[bool] = None


class AgentSkill(BaseModel):
    """A skill that an agent can perform."""

    model_config = {'populate_by_name': True}

    id: str = Field(...)
    name: str = Field(...)
    description: str = Field(...)
    tags: List[str] = Field(default_factory=list)
    examples: List[str] = Field(default_factory=list)
    input_modes: List[str] = Field(default_factory=list, alias='inputModes')
    output_modes: List[str] = Field(default_factory=list, alias='outputModes')


class AuthenticationScheme(BaseModel):
    """Legacy authentication scheme (kept for backwards compat)."""

    scheme: str = Field(...)
    description: Optional[str] = None


class AgentCard(BaseModel):
    """A2A Agent Card — full spec parity with proto + Rust types.rs."""

    model_config = {'populate_by_name': True}

    name: str = Field(...)
    description: str = Field(...)
    url: str = Field(...)
    version: str = Field('1.0')
    protocol_version: str = Field('0.3', alias='protocolVersion')
    preferred_transport: Optional[str] = Field(None, alias='preferredTransport')
    additional_interfaces: Optional[List[AgentInterface]] = Field(
        default_factory=list, alias='additionalInterfaces'
    )
    provider: Optional[AgentProvider] = None
    capabilities: AgentCapabilities = Field(default_factory=AgentCapabilities)
    skills: List[AgentSkill] = Field(default_factory=list)
    default_input_modes: List[str] = Field(
        default_factory=list, alias='defaultInputModes'
    )
    default_output_modes: List[str] = Field(
        default_factory=list, alias='defaultOutputModes'
    )
    icon_url: Optional[str] = Field(None, alias='iconUrl')
    documentation_url: Optional[str] = Field(None, alias='documentationUrl')
    security_schemes: Dict[str, SecurityScheme] = Field(
        default_factory=dict, alias='securitySchemes'
    )
    security: List[SecurityRequirement] = Field(default_factory=list)
    supports_authenticated_extended_card: bool = Field(
        False, alias='supportsAuthenticatedExtendedCard'
    )
    signatures: List[AgentCardSignature] = Field(default_factory=list)

    # Legacy field preserved for backwards compat
    authentication: List[AuthenticationScheme] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════
# Legacy LiveKit interface types (kept for backwards compat)
# ═══════════════════════════════════════════════════════════════════════════


class LiveKitInterface(BaseModel):
    """Configuration for LiveKit media interface."""

    token_endpoint: str = Field(...)
    join_url_template: Optional[str] = None
    server_managed: bool = True


class AdditionalInterfaces(BaseModel):
    """Legacy additional interfaces (use AgentCard.additional_interfaces)."""

    model_config = {'extra': 'allow'}
    livekit: Optional[LiveKitInterface] = None


# ═══════════════════════════════════════════════════════════════════════════
# JSON-RPC types
# ═══════════════════════════════════════════════════════════════════════════


class JSONRPCRequest(BaseModel):
    """JSON-RPC 2.0 request."""

    jsonrpc: Literal['2.0'] = '2.0'
    method: str = Field(...)
    params: Optional[Dict[str, Any]] = None
    id: Optional[Union[str, int]] = None


class JSONRPCResponse(BaseModel):
    """JSON-RPC 2.0 response."""

    jsonrpc: Literal['2.0'] = '2.0'
    id: Optional[Union[str, int]] = None
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None


class JSONRPCError(BaseModel):
    """JSON-RPC 2.0 error."""

    code: int = Field(...)
    message: str = Field(...)
    data: Optional[Any] = None


# ═══════════════════════════════════════════════════════════════════════════
# Request / response models for JSON-RPC methods
# ═══════════════════════════════════════════════════════════════════════════


class SendMessageRequest(BaseModel):
    """Request for message/send — spec-aligned."""

    model_config = {'populate_by_name': True}

    message: Message = Field(...)
    configuration: Optional[SendMessageConfiguration] = None
    metadata: Optional[Dict[str, Any]] = None

    # Legacy fields — kept so old callers still work
    task_id: Optional[str] = Field(None, alias='taskId')
    skill_id: Optional[str] = Field(None, alias='skillId')


class SendMessageResponse(BaseModel):
    """Response for message/send."""

    task: Task = Field(...)
    message: Optional[Message] = None


class GetTaskRequest(BaseModel):
    """Request for tasks/get."""

    model_config = {'populate_by_name': True}

    task_id: str = Field(..., alias='id')
    history_length: Optional[int] = Field(None, alias='historyLength')


class GetTaskResponse(BaseModel):
    """Response for tasks/get."""

    task: Task = Field(...)


class CancelTaskRequest(BaseModel):
    """Request to cancel a task."""

    model_config = {'populate_by_name': True}

    task_id: str = Field(..., alias='id')


class CancelTaskResponse(BaseModel):
    """Response confirming task cancellation."""

    task: Task = Field(...)


class StreamMessageRequest(BaseModel):
    """Request for message/stream — spec-aligned."""

    model_config = {'populate_by_name': True}

    message: Message = Field(...)
    configuration: Optional[SendMessageConfiguration] = None
    metadata: Optional[Dict[str, Any]] = None

    # Legacy fields
    task_id: Optional[str] = Field(None, alias='taskId')
    skill_id: Optional[str] = Field(None, alias='skillId')


class StreamingMessageResponse(BaseModel):
    """Wrapper for streaming events."""

    event: TaskStatusUpdateEvent = Field(...)


# ═══════════════════════════════════════════════════════════════════════════
# Push notification config request / response types
# ═══════════════════════════════════════════════════════════════════════════


class SetPushNotificationConfigRequest(BaseModel):
    """Request to create/set push notification config for a task."""

    model_config = {'populate_by_name': True}

    task_id: str = Field(..., alias='id')
    push_notification_config: PushNotificationConfig = Field(
        ..., alias='pushNotificationConfig'
    )


class GetPushNotificationConfigRequest(BaseModel):
    """Request to get push notification config for a task."""

    model_config = {'populate_by_name': True}

    task_id: str = Field(..., alias='id')
    config_id: Optional[str] = Field(None, alias='configId')


class ListPushNotificationConfigsRequest(BaseModel):
    """Request to list push notification configs for a task."""

    model_config = {'populate_by_name': True}

    task_id: str = Field(..., alias='id')


class DeletePushNotificationConfigRequest(BaseModel):
    """Request to delete a push notification config."""

    model_config = {'populate_by_name': True}

    task_id: str = Field(..., alias='id')
    config_id: Optional[str] = Field(None, alias='configId')


# ═══════════════════════════════════════════════════════════════════════════
# Media types (unchanged from original for backwards compat)
# ═══════════════════════════════════════════════════════════════════════════


class MediaRequestRequest(BaseModel):
    """Request to create or join a media session."""

    room_name: Optional[str] = None
    participant_identity: str = Field(...)
    role: str = 'participant'
    metadata: Optional[Dict[str, Any]] = None
    max_participants: int = 50


class MediaRequestResponse(BaseModel):
    """Response containing media session information."""

    task: Task = Field(...)
    room_name: str = Field(...)
    room_sid: Optional[str] = None
    join_url: str = Field(...)
    access_token: str = Field(...)
    participant_identity: str = Field(...)
    expires_at: datetime = Field(...)


class MediaJoinRequest(BaseModel):
    """Request to join an existing media session."""

    room_name: str = Field(...)
    participant_identity: str = Field(...)
    role: str = 'participant'
    metadata: Optional[str] = None


class MediaJoinResponse(BaseModel):
    """Response for joining a media session."""

    join_url: str = Field(...)
    access_token: str = Field(...)
    participant_identity: str = Field(...)
    expires_at: datetime = Field(...)


class LiveKitTokenRequest(BaseModel):
    """Request for a LiveKit access token."""

    room_name: str = Field(...)
    identity: str = Field(...)
    role: str = 'participant'
    metadata: Optional[str] = None
    ttl_minutes: int = Field(60, ge=1, le=1440)


class LiveKitTokenResponse(BaseModel):
    """Response containing LiveKit access token."""

    access_token: str = Field(...)
    join_url: str = Field(...)
    expires_at: datetime = Field(...)


# Rebuild Task to resolve forward references
Task.model_rebuild()
