"""
A2A-compliant error handling for CodeTether.

This module provides error classes and utilities that comply with the A2A protocol
specification for error handling, including:

1. A2A-specific error codes (-32001 to -32009)
2. Standard JSON-RPC 2.0 error codes (-32700 to -32603)
3. JSON-RPC error response formatting
4. RFC 9457 Problem Details format for REST binding
5. Exception conversion utilities and decorators

A2A Error Codes:
- -32001: TaskNotFoundError (HTTP 404)
- -32002: TaskNotCancelableError (HTTP 409)
- -32003: PushNotificationNotSupportedError (HTTP 400)
- -32004: UnsupportedOperationError (HTTP 400)
- -32005: ContentTypeNotSupportedError (HTTP 415)
- -32006: InvalidAgentResponseError (HTTP 502)
- -32007: ExtendedAgentCardNotConfiguredError (HTTP 400)
- -32008: ExtensionSupportRequiredError (HTTP 400)
- -32009: VersionNotSupportedError (HTTP 400)

JSON-RPC Error Codes:
- -32700: ParseError (HTTP 400)
- -32600: InvalidRequest (HTTP 400)
- -32601: MethodNotFound (HTTP 404)
- -32602: InvalidParams (HTTP 400)
- -32603: InternalError (HTTP 500)
"""

from __future__ import annotations

import functools
import json
import logging
import traceback
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union

from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# =============================================================================
# Base A2A Error Classes
# =============================================================================


class A2AError(Exception):
    """
    Base exception class for all A2A protocol errors.

    Subclasses should define:
    - code: JSON-RPC error code (negative integer)
    - http_status: HTTP status code for REST binding
    - message: Default error message

    Attributes:
        code: JSON-RPC error code
        http_status: HTTP status code
        message: Human-readable error message
        data: Additional error data (optional)
        task_id: Related task ID (optional)
    """

    code: int = -32000  # Generic server error
    http_status: int = 500
    message: str = 'A2A protocol error'

    def __init__(
        self,
        message: Optional[str] = None,
        data: Optional[Any] = None,
        task_id: Optional[str] = None,
    ):
        self._message = message or self.__class__.message
        self.data = data
        self.task_id = task_id
        super().__init__(self._message)

    @property
    def error_message(self) -> str:
        """Get the error message."""
        return self._message

    def to_jsonrpc_error(
        self, request_id: Optional[Union[str, int]] = None
    ) -> Dict[str, Any]:
        """
        Convert to JSON-RPC 2.0 error response format.

        Args:
            request_id: The JSON-RPC request ID (if any)

        Returns:
            JSON-RPC 2.0 error response dict
        """
        error: Dict[str, Any] = {
            'code': self.code,
            'message': self._message,
        }

        if self.data is not None:
            error['data'] = self.data
        elif self.task_id:
            error['data'] = {'task_id': self.task_id}

        return {
            'jsonrpc': '2.0',
            'id': request_id,
            'error': error,
        }

    def to_problem_details(
        self,
        request: Optional[Request] = None,
        instance: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Convert to RFC 9457 Problem Details format for REST binding.

        Args:
            request: FastAPI request object (for instance URL)
            instance: Override for the instance URI

        Returns:
            RFC 9457 Problem Details dict
        """
        problem = {
            'type': f'urn:a2a:error:{self.__class__.__name__}',
            'title': self.__class__.__name__.replace('Error', ' Error'),
            'status': self.http_status,
            'detail': self._message,
            'a2a_code': self.code,
        }

        # Add instance URI
        if instance:
            problem['instance'] = instance
        elif request:
            problem['instance'] = str(request.url)

        # Add task_id if present
        if self.task_id:
            problem['task_id'] = self.task_id

        # Add additional data
        if self.data:
            problem['additional_data'] = self.data

        # Add timestamp
        problem['timestamp'] = datetime.now(timezone.utc).isoformat()

        return problem

    def to_http_response(
        self,
        request: Optional[Request] = None,
        use_problem_details: bool = True,
    ) -> JSONResponse:
        """
        Convert to FastAPI JSONResponse.

        Args:
            request: FastAPI request object
            use_problem_details: Use RFC 9457 format (default True)

        Returns:
            FastAPI JSONResponse
        """
        if use_problem_details:
            content = self.to_problem_details(request)
            media_type = 'application/problem+json'
        else:
            content = {
                'error': {
                    'code': self.code,
                    'message': self._message,
                }
            }
            if self.data:
                content['error']['data'] = self.data
            media_type = 'application/json'

        return JSONResponse(
            status_code=self.http_status,
            content=content,
            media_type=media_type,
        )


# =============================================================================
# A2A-Specific Error Classes (-32001 to -32009)
# =============================================================================


class TaskNotFoundError(A2AError):
    """
    Error code: -32001
    HTTP status: 404

    Raised when a requested task cannot be found.
    """

    code = -32001
    http_status = 404
    message = 'Task not found'

    def __init__(
        self,
        task_id: str,
        message: Optional[str] = None,
        data: Optional[Any] = None,
    ):
        super().__init__(
            message=message or f"Task '{task_id}' not found",
            data=data,
            task_id=task_id,
        )


class TaskNotCancelableError(A2AError):
    """
    Error code: -32002
    HTTP status: 409

    Raised when a task cannot be cancelled (e.g., already completed).
    """

    code = -32002
    http_status = 409
    message = 'Task cannot be cancelled'

    def __init__(
        self,
        task_id: str,
        reason: Optional[str] = None,
        message: Optional[str] = None,
        data: Optional[Any] = None,
    ):
        reason_text = reason or 'task is in a non-cancelable state'
        super().__init__(
            message=message
            or f"Task '{task_id}' cannot be cancelled: {reason_text}",
            data=data or {'reason': reason_text},
            task_id=task_id,
        )


class PushNotificationNotSupportedError(A2AError):
    """
    Error code: -32003
    HTTP status: 400

    Raised when push notifications are requested but not supported.
    """

    code = -32003
    http_status = 400
    message = 'Push notifications are not supported'

    def __init__(
        self,
        message: Optional[str] = None,
        data: Optional[Any] = None,
    ):
        super().__init__(
            message=message or 'This agent does not support push notifications',
            data=data,
        )


class UnsupportedOperationError(A2AError):
    """
    Error code: -32004
    HTTP status: 400

    Raised when an operation is not supported by the agent.
    """

    code = -32004
    http_status = 400
    message = 'Operation not supported'

    def __init__(
        self,
        operation: str,
        message: Optional[str] = None,
        data: Optional[Any] = None,
    ):
        super().__init__(
            message=message
            or f"Operation '{operation}' is not supported by this agent",
            data=data or {'operation': operation},
        )


class ContentTypeNotSupportedError(A2AError):
    """
    Error code: -32005
    HTTP status: 415

    Raised when the content type is not supported.
    """

    code = -32005
    http_status = 415
    message = 'Content type not supported'

    def __init__(
        self,
        content_type: str,
        supported_types: Optional[List[str]] = None,
        message: Optional[str] = None,
        data: Optional[Any] = None,
    ):
        supported = supported_types or ['application/json']
        super().__init__(
            message=message
            or f"Content type '{content_type}' is not supported. Supported: {', '.join(supported)}",
            data=data
            or {
                'content_type': content_type,
                'supported_types': supported,
            },
        )


class InvalidAgentResponseError(A2AError):
    """
    Error code: -32006
    HTTP status: 502

    Raised when an agent returns an invalid response.
    """

    code = -32006
    http_status = 502
    message = 'Invalid agent response'

    def __init__(
        self,
        agent_name: Optional[str] = None,
        reason: Optional[str] = None,
        message: Optional[str] = None,
        data: Optional[Any] = None,
    ):
        detail = reason or 'response did not match expected format'
        agent_info = f" from agent '{agent_name}'" if agent_name else ''
        super().__init__(
            message=message or f'Invalid response{agent_info}: {detail}',
            data=data
            or {
                'agent_name': agent_name,
                'reason': reason,
            },
        )


class ExtendedAgentCardNotConfiguredError(A2AError):
    """
    Error code: -32007
    HTTP status: 400

    Raised when extended agent card features are required but not configured.
    """

    code = -32007
    http_status = 400
    message = 'Extended agent card not configured'

    def __init__(
        self,
        required_feature: Optional[str] = None,
        message: Optional[str] = None,
        data: Optional[Any] = None,
    ):
        feature_info = (
            f' (required: {required_feature})' if required_feature else ''
        )
        super().__init__(
            message=message
            or f'Extended agent card is not configured{feature_info}',
            data=data or {'required_feature': required_feature},
        )


class ExtensionSupportRequiredError(A2AError):
    """
    Error code: -32008
    HTTP status: 400

    Raised when a required protocol extension is not supported.
    """

    code = -32008
    http_status = 400
    message = 'Extension support required'

    def __init__(
        self,
        extension_uri: str,
        message: Optional[str] = None,
        data: Optional[Any] = None,
    ):
        super().__init__(
            message=message
            or f'Protocol extension required but not supported: {extension_uri}',
            data=data or {'extension_uri': extension_uri},
        )


class VersionNotSupportedError(A2AError):
    """
    Error code: -32009
    HTTP status: 400

    Raised when the requested protocol version is not supported.
    """

    code = -32009
    http_status = 400
    message = 'Version not supported'

    def __init__(
        self,
        requested_version: str,
        supported_versions: Optional[List[str]] = None,
        message: Optional[str] = None,
        data: Optional[Any] = None,
    ):
        supported = supported_versions or ['1.0']
        super().__init__(
            message=message
            or f"Protocol version '{requested_version}' is not supported. Supported: {', '.join(supported)}",
            data=data
            or {
                'requested_version': requested_version,
                'supported_versions': supported,
            },
        )


# =============================================================================
# JSON-RPC Standard Error Classes (-32700 to -32603)
# =============================================================================


class ParseError(A2AError):
    """
    Error code: -32700
    HTTP status: 400

    Invalid JSON was received by the server.
    """

    code = -32700
    http_status = 400
    message = 'Parse error'

    def __init__(
        self,
        detail: Optional[str] = None,
        message: Optional[str] = None,
        data: Optional[Any] = None,
    ):
        super().__init__(
            message=message or f'Invalid JSON: {detail}'
            if detail
            else 'Invalid JSON was received',
            data=data or {'detail': detail},
        )


class InvalidRequest(A2AError):
    """
    Error code: -32600
    HTTP status: 400

    The JSON sent is not a valid Request object.
    """

    code = -32600
    http_status = 400
    message = 'Invalid Request'

    def __init__(
        self,
        reason: Optional[str] = None,
        message: Optional[str] = None,
        data: Optional[Any] = None,
    ):
        super().__init__(
            message=message or f'Invalid request: {reason}'
            if reason
            else 'Invalid request object',
            data=data or {'reason': reason},
        )


class MethodNotFound(A2AError):
    """
    Error code: -32601
    HTTP status: 404

    The method does not exist or is not available.
    """

    code = -32601
    http_status = 404
    message = 'Method not found'

    def __init__(
        self,
        method: str,
        available_methods: Optional[List[str]] = None,
        message: Optional[str] = None,
        data: Optional[Any] = None,
    ):
        super().__init__(
            message=message or f"Method '{method}' not found",
            data=data
            or {
                'method': method,
                'available_methods': available_methods,
            },
        )


class InvalidParams(A2AError):
    """
    Error code: -32602
    HTTP status: 400

    Invalid method parameters.
    """

    code = -32602
    http_status = 400
    message = 'Invalid params'

    def __init__(
        self,
        param_errors: Optional[List[Dict[str, Any]]] = None,
        message: Optional[str] = None,
        data: Optional[Any] = None,
    ):
        if param_errors:
            error_details = '; '.join(
                f'{e.get("param", "unknown")}: {e.get("error", "invalid")}'
                for e in param_errors
            )
            msg = message or f'Invalid parameters: {error_details}'
        else:
            msg = message or 'Invalid method parameters'

        super().__init__(
            message=msg,
            data=data or {'param_errors': param_errors},
        )


class InternalError(A2AError):
    """
    Error code: -32603
    HTTP status: 500

    Internal JSON-RPC error.
    """

    code = -32603
    http_status = 500
    message = 'Internal error'

    def __init__(
        self,
        detail: Optional[str] = None,
        message: Optional[str] = None,
        data: Optional[Any] = None,
        include_traceback: bool = False,
    ):
        if include_traceback:
            tb = traceback.format_exc()
            data = data or {}
            if isinstance(data, dict):
                data['traceback'] = tb

        super().__init__(
            message=message or f'Internal error: {detail}'
            if detail
            else 'Internal server error',
            data=data,
        )


# =============================================================================
# Error Registry and Conversion
# =============================================================================


# Map of error codes to error classes
ERROR_CODE_MAP: Dict[int, Type[A2AError]] = {
    # A2A errors
    -32001: TaskNotFoundError,
    -32002: TaskNotCancelableError,
    -32003: PushNotificationNotSupportedError,
    -32004: UnsupportedOperationError,
    -32005: ContentTypeNotSupportedError,
    -32006: InvalidAgentResponseError,
    -32007: ExtendedAgentCardNotConfiguredError,
    -32008: ExtensionSupportRequiredError,
    -32009: VersionNotSupportedError,
    # JSON-RPC errors
    -32700: ParseError,
    -32600: InvalidRequest,
    -32601: MethodNotFound,
    -32602: InvalidParams,
    -32603: InternalError,
}


# Map of HTTP status codes to default error classes
HTTP_STATUS_MAP: Dict[int, Type[A2AError]] = {
    400: InvalidRequest,
    404: TaskNotFoundError,
    409: TaskNotCancelableError,
    415: ContentTypeNotSupportedError,
    500: InternalError,
    502: InvalidAgentResponseError,
}


def error_from_code(
    code: int,
    message: Optional[str] = None,
    data: Optional[Any] = None,
) -> A2AError:
    """
    Create an A2A error from an error code.

    Args:
        code: JSON-RPC error code
        message: Optional custom message
        data: Optional additional data

    Returns:
        Appropriate A2AError subclass instance
    """
    error_class = ERROR_CODE_MAP.get(code, A2AError)
    return error_class(message=message, data=data)


def error_from_http_status(
    status: int,
    message: Optional[str] = None,
    data: Optional[Any] = None,
) -> A2AError:
    """
    Create an A2A error from an HTTP status code.

    Args:
        status: HTTP status code
        message: Optional custom message
        data: Optional additional data

    Returns:
        Appropriate A2AError subclass instance
    """
    error_class = HTTP_STATUS_MAP.get(status, InternalError)
    return error_class(message=message, data=data)


# =============================================================================
# Exception Conversion Utilities
# =============================================================================


def convert_exception(
    exc: Exception, task_id: Optional[str] = None
) -> A2AError:
    """
    Convert any exception to an A2A error.

    This handles conversion from:
    - A2AError (returned as-is)
    - FastAPI HTTPException
    - ValueError/TypeError (InvalidParams)
    - KeyError (TaskNotFoundError)
    - NotImplementedError (UnsupportedOperationError)
    - TaskLimitExceeded (custom error)
    - Any other exception (InternalError)

    Args:
        exc: The exception to convert
        task_id: Optional task ID to include in error

    Returns:
        A2AError instance
    """
    # Already an A2A error
    if isinstance(exc, A2AError):
        if task_id and not exc.task_id:
            exc.task_id = task_id
        return exc

    # FastAPI HTTPException
    if isinstance(exc, HTTPException):
        return error_from_http_status(
            exc.status_code,
            message=str(exc.detail),
            data={'task_id': task_id} if task_id else None,
        )

    # ValueError/TypeError -> InvalidParams
    if isinstance(exc, (ValueError, TypeError)):
        return InvalidParams(
            message=str(exc),
            data={'task_id': task_id} if task_id else None,
        )

    # KeyError -> TaskNotFoundError (common pattern)
    if isinstance(exc, KeyError):
        key = str(exc.args[0]) if exc.args else 'unknown'
        if task_id:
            return TaskNotFoundError(task_id=task_id)
        return TaskNotFoundError(
            task_id=key,
            message=f'Resource not found: {key}',
        )

    # NotImplementedError -> UnsupportedOperationError
    if isinstance(exc, NotImplementedError):
        return UnsupportedOperationError(
            operation=str(exc) or 'unknown',
            data={'task_id': task_id} if task_id else None,
        )

    # json.JSONDecodeError -> ParseError
    if isinstance(exc, json.JSONDecodeError):
        return ParseError(
            detail=f'at position {exc.pos}: {exc.msg}',
            data={'task_id': task_id} if task_id else None,
        )

    # TaskLimitExceeded (from task_queue.py)
    # Import locally to avoid circular imports
    try:
        from a2a_server.task_queue import TaskLimitExceeded

        if isinstance(exc, TaskLimitExceeded):
            return InvalidRequest(
                reason='task_limit_exceeded',
                message=str(exc),
                data={
                    'task_id': task_id,
                    'tasks_used': exc.tasks_used,
                    'tasks_limit': exc.tasks_limit,
                    'running_count': exc.running_count,
                    'concurrency_limit': exc.concurrency_limit,
                },
            )
    except ImportError:
        pass

    # Default to InternalError
    return InternalError(
        detail=str(exc),
        data={
            'task_id': task_id,
            'exception_type': type(exc).__name__,
        },
    )


# =============================================================================
# Decorators and Middleware
# =============================================================================


T = TypeVar('T')


def a2a_error_handler(
    request_id_param: Optional[str] = None,
    task_id_param: Optional[str] = None,
    use_jsonrpc: bool = True,
    log_errors: bool = True,
):
    """
    Decorator to convert exceptions to A2A error responses.

    Can be used for both JSON-RPC and REST endpoints.

    Args:
        request_id_param: Name of the request ID parameter (for JSON-RPC)
        task_id_param: Name of the task ID parameter
        use_jsonrpc: Return JSON-RPC format (True) or Problem Details (False)
        log_errors: Log errors to the logger

    Example:
        @a2a_error_handler(request_id_param="id", task_id_param="task_id")
        async def handle_get_task(id: str, task_id: str) -> dict:
            ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            request_id = (
                kwargs.get(request_id_param) if request_id_param else None
            )
            task_id = kwargs.get(task_id_param) if task_id_param else None

            try:
                return await func(*args, **kwargs)
            except A2AError as e:
                if task_id and not e.task_id:
                    e.task_id = task_id

                if log_errors:
                    logger.warning(
                        f'A2A error in {func.__name__}: [{e.code}] {e.error_message}'
                    )

                if use_jsonrpc:
                    return e.to_jsonrpc_error(request_id)
                return e.to_problem_details()

            except Exception as exc:
                a2a_error = convert_exception(exc, task_id)

                if log_errors:
                    logger.error(
                        f'Exception in {func.__name__}: {type(exc).__name__}: {exc}',
                        exc_info=True,
                    )

                if use_jsonrpc:
                    return a2a_error.to_jsonrpc_error(request_id)
                return a2a_error.to_problem_details()

        return wrapper

    return decorator


async def a2a_exception_middleware(request: Request, call_next):
    """
    FastAPI middleware to catch exceptions and return A2A error responses.

    Usage:
        app.middleware("http")(a2a_exception_middleware)

    This middleware:
    1. Catches any unhandled exceptions
    2. Converts them to A2A errors
    3. Returns appropriate JSON-RPC or Problem Details response
    """
    try:
        response = await call_next(request)
        return response
    except A2AError as e:
        logger.warning(f'A2A error: [{e.code}] {e.error_message}')
        return e.to_http_response(request)
    except HTTPException as e:
        a2a_error = error_from_http_status(e.status_code, str(e.detail))
        return a2a_error.to_http_response(request)
    except Exception as exc:
        logger.error(
            f'Unhandled exception: {type(exc).__name__}: {exc}', exc_info=True
        )
        a2a_error = convert_exception(exc)
        return a2a_error.to_http_response(request)


def create_exception_handlers() -> Dict[Type[Exception], Callable]:
    """
    Create FastAPI exception handlers for A2A errors.

    Usage:
        handlers = create_exception_handlers()
        for exc_class, handler in handlers.items():
            app.add_exception_handler(exc_class, handler)
    """

    async def handle_a2a_error(request: Request, exc: A2AError) -> Response:
        logger.warning(f'A2A error: [{exc.code}] {exc.error_message}')
        return exc.to_http_response(request)

    async def handle_http_exception(
        request: Request, exc: HTTPException
    ) -> Response:
        a2a_error = error_from_http_status(exc.status_code, str(exc.detail))
        return a2a_error.to_http_response(request)

    async def handle_value_error(request: Request, exc: ValueError) -> Response:
        a2a_error = InvalidParams(message=str(exc))
        return a2a_error.to_http_response(request)

    async def handle_json_error(
        request: Request, exc: json.JSONDecodeError
    ) -> Response:
        a2a_error = ParseError(detail=f'at position {exc.pos}: {exc.msg}')
        return a2a_error.to_http_response(request)

    async def handle_generic_exception(
        request: Request, exc: Exception
    ) -> Response:
        logger.error(
            f'Unhandled exception: {type(exc).__name__}: {exc}', exc_info=True
        )
        a2a_error = InternalError(detail=str(exc))
        return a2a_error.to_http_response(request)

    return {
        A2AError: handle_a2a_error,
        HTTPException: handle_http_exception,
        ValueError: handle_value_error,
        json.JSONDecodeError: handle_json_error,
        Exception: handle_generic_exception,
    }


# =============================================================================
# JSON-RPC Response Builders
# =============================================================================


def jsonrpc_success(
    result: Any,
    request_id: Optional[Union[str, int]] = None,
) -> Dict[str, Any]:
    """
    Build a JSON-RPC 2.0 success response.

    Args:
        result: The result to return
        request_id: The request ID

    Returns:
        JSON-RPC 2.0 response dict
    """
    return {
        'jsonrpc': '2.0',
        'id': request_id,
        'result': result,
    }


def jsonrpc_error(
    code: int,
    message: str,
    data: Optional[Any] = None,
    request_id: Optional[Union[str, int]] = None,
) -> Dict[str, Any]:
    """
    Build a JSON-RPC 2.0 error response.

    Args:
        code: Error code
        message: Error message
        data: Additional error data
        request_id: The request ID

    Returns:
        JSON-RPC 2.0 error response dict
    """
    error: Dict[str, Any] = {
        'code': code,
        'message': message,
    }
    if data is not None:
        error['data'] = data

    return {
        'jsonrpc': '2.0',
        'id': request_id,
        'error': error,
    }


def jsonrpc_error_from_exception(
    exc: Exception,
    request_id: Optional[Union[str, int]] = None,
    task_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build a JSON-RPC 2.0 error response from an exception.

    Args:
        exc: The exception
        request_id: The request ID
        task_id: Optional task ID

    Returns:
        JSON-RPC 2.0 error response dict
    """
    a2a_error = convert_exception(exc, task_id)
    return a2a_error.to_jsonrpc_error(request_id)


# =============================================================================
# Pydantic Models for Error Responses
# =============================================================================


class JSONRPCErrorData(BaseModel):
    """Pydantic model for JSON-RPC error data."""

    code: int = Field(..., description='Error code')
    message: str = Field(..., description='Error message')
    data: Optional[Any] = Field(None, description='Additional error data')


class JSONRPCErrorResponse(BaseModel):
    """Pydantic model for JSON-RPC error response."""

    jsonrpc: str = Field('2.0', description='JSON-RPC version')
    id: Optional[Union[str, int]] = Field(None, description='Request ID')
    error: JSONRPCErrorData = Field(..., description='Error data')


class ProblemDetails(BaseModel):
    """
    Pydantic model for RFC 9457 Problem Details.

    Used for REST binding error responses.
    """

    type: str = Field(
        ..., description='URI reference identifying the problem type'
    )
    title: str = Field(..., description='Short summary of the problem type')
    status: int = Field(..., description='HTTP status code')
    detail: str = Field(
        ..., description='Explanation specific to this occurrence'
    )
    instance: Optional[str] = Field(
        None, description='URI reference for this occurrence'
    )
    a2a_code: Optional[int] = Field(None, description='A2A error code')
    task_id: Optional[str] = Field(None, description='Related task ID')
    timestamp: Optional[str] = Field(None, description='ISO 8601 timestamp')
    additional_data: Optional[Dict[str, Any]] = Field(
        None, description='Additional error data'
    )


# =============================================================================
# Utility Functions
# =============================================================================


def is_a2a_error_code(code: int) -> bool:
    """Check if an error code is an A2A-specific error."""
    return -32009 <= code <= -32001


def is_jsonrpc_error_code(code: int) -> bool:
    """Check if an error code is a standard JSON-RPC error."""
    return -32700 <= code <= -32600 or code == -32603


def get_error_description(code: int) -> str:
    """Get a human-readable description for an error code."""
    descriptions = {
        # A2A errors
        -32001: 'Task not found',
        -32002: 'Task cannot be cancelled',
        -32003: 'Push notifications not supported',
        -32004: 'Operation not supported',
        -32005: 'Content type not supported',
        -32006: 'Invalid agent response',
        -32007: 'Extended agent card not configured',
        -32008: 'Extension support required',
        -32009: 'Version not supported',
        # JSON-RPC errors
        -32700: 'Parse error - Invalid JSON',
        -32600: 'Invalid request',
        -32601: 'Method not found',
        -32602: 'Invalid params',
        -32603: 'Internal error',
    }
    return descriptions.get(code, f'Unknown error (code: {code})')


__all__ = [
    # Base class
    'A2AError',
    # A2A errors
    'TaskNotFoundError',
    'TaskNotCancelableError',
    'PushNotificationNotSupportedError',
    'UnsupportedOperationError',
    'ContentTypeNotSupportedError',
    'InvalidAgentResponseError',
    'ExtendedAgentCardNotConfiguredError',
    'ExtensionSupportRequiredError',
    'VersionNotSupportedError',
    # JSON-RPC errors
    'ParseError',
    'InvalidRequest',
    'MethodNotFound',
    'InvalidParams',
    'InternalError',
    # Conversion utilities
    'error_from_code',
    'error_from_http_status',
    'convert_exception',
    # Decorators and middleware
    'a2a_error_handler',
    'a2a_exception_middleware',
    'create_exception_handlers',
    # JSON-RPC builders
    'jsonrpc_success',
    'jsonrpc_error',
    'jsonrpc_error_from_exception',
    # Pydantic models
    'JSONRPCErrorData',
    'JSONRPCErrorResponse',
    'ProblemDetails',
    # Maps
    'ERROR_CODE_MAP',
    'HTTP_STATUS_MAP',
    # Utilities
    'is_a2a_error_code',
    'is_jsonrpc_error_code',
    'get_error_description',
]
