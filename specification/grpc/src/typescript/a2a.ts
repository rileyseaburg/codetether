/* eslint-disable */
import * as _m0 from "protobufjs/minimal";
import { Observable } from "rxjs";
import { map } from "rxjs/operators";
import { Empty } from "./google/protobuf/empty";
import { Struct } from "./google/protobuf/struct";
import { Timestamp } from "./google/protobuf/timestamp";

export const protobufPackage = "a2a.v1";

/** Older protoc compilers don't understand edition yet. */

/**
 * --8<-- [start:TaskState]
 * The set of states a Task can be in.
 */
export enum TaskState {
  TASK_STATE_UNSPECIFIED = 0,
  /** TASK_STATE_SUBMITTED - Represents the status that acknowledges a task is created */
  TASK_STATE_SUBMITTED = 1,
  /** TASK_STATE_WORKING - Represents the status that a task is actively being processed */
  TASK_STATE_WORKING = 2,
  /** TASK_STATE_COMPLETED - Represents the status a task is finished. This is a terminal state */
  TASK_STATE_COMPLETED = 3,
  /** TASK_STATE_FAILED - Represents the status a task is done but failed. This is a terminal state */
  TASK_STATE_FAILED = 4,
  /**
   * TASK_STATE_CANCELLED - Represents the status a task was cancelled before it finished.
   * This is a terminal state.
   */
  TASK_STATE_CANCELLED = 5,
  /**
   * TASK_STATE_INPUT_REQUIRED - Represents the status that the task requires information to complete.
   * This is an interrupted state.
   */
  TASK_STATE_INPUT_REQUIRED = 6,
  /**
   * TASK_STATE_REJECTED - Represents the status that the agent has decided to not perform the task.
   * This may be done during initial task creation or later once an agent
   * has determined it can't or won't proceed. This is a terminal state.
   */
  TASK_STATE_REJECTED = 7,
  /**
   * TASK_STATE_AUTH_REQUIRED - Represents the state that some authentication is needed from the upstream
   * client. Authentication is expected to come out-of-band thus this is not
   * an interrupted or terminal state.
   */
  TASK_STATE_AUTH_REQUIRED = 8,
  UNRECOGNIZED = -1,
}

export function taskStateFromJSON(object: any): TaskState {
  switch (object) {
    case 0:
    case "TASK_STATE_UNSPECIFIED":
      return TaskState.TASK_STATE_UNSPECIFIED;
    case 1:
    case "TASK_STATE_SUBMITTED":
      return TaskState.TASK_STATE_SUBMITTED;
    case 2:
    case "TASK_STATE_WORKING":
      return TaskState.TASK_STATE_WORKING;
    case 3:
    case "TASK_STATE_COMPLETED":
      return TaskState.TASK_STATE_COMPLETED;
    case 4:
    case "TASK_STATE_FAILED":
      return TaskState.TASK_STATE_FAILED;
    case 5:
    case "TASK_STATE_CANCELLED":
      return TaskState.TASK_STATE_CANCELLED;
    case 6:
    case "TASK_STATE_INPUT_REQUIRED":
      return TaskState.TASK_STATE_INPUT_REQUIRED;
    case 7:
    case "TASK_STATE_REJECTED":
      return TaskState.TASK_STATE_REJECTED;
    case 8:
    case "TASK_STATE_AUTH_REQUIRED":
      return TaskState.TASK_STATE_AUTH_REQUIRED;
    case -1:
    case "UNRECOGNIZED":
    default:
      return TaskState.UNRECOGNIZED;
  }
}

export function taskStateToJSON(object: TaskState): string {
  switch (object) {
    case TaskState.TASK_STATE_UNSPECIFIED:
      return "TASK_STATE_UNSPECIFIED";
    case TaskState.TASK_STATE_SUBMITTED:
      return "TASK_STATE_SUBMITTED";
    case TaskState.TASK_STATE_WORKING:
      return "TASK_STATE_WORKING";
    case TaskState.TASK_STATE_COMPLETED:
      return "TASK_STATE_COMPLETED";
    case TaskState.TASK_STATE_FAILED:
      return "TASK_STATE_FAILED";
    case TaskState.TASK_STATE_CANCELLED:
      return "TASK_STATE_CANCELLED";
    case TaskState.TASK_STATE_INPUT_REQUIRED:
      return "TASK_STATE_INPUT_REQUIRED";
    case TaskState.TASK_STATE_REJECTED:
      return "TASK_STATE_REJECTED";
    case TaskState.TASK_STATE_AUTH_REQUIRED:
      return "TASK_STATE_AUTH_REQUIRED";
    case TaskState.UNRECOGNIZED:
    default:
      return "UNRECOGNIZED";
  }
}

export enum Role {
  ROLE_UNSPECIFIED = 0,
  /** ROLE_USER - USER role refers to communication from the client to the server. */
  ROLE_USER = 1,
  /** ROLE_AGENT - AGENT role refers to communication from the server to the client. */
  ROLE_AGENT = 2,
  UNRECOGNIZED = -1,
}

export function roleFromJSON(object: any): Role {
  switch (object) {
    case 0:
    case "ROLE_UNSPECIFIED":
      return Role.ROLE_UNSPECIFIED;
    case 1:
    case "ROLE_USER":
      return Role.ROLE_USER;
    case 2:
    case "ROLE_AGENT":
      return Role.ROLE_AGENT;
    case -1:
    case "UNRECOGNIZED":
    default:
      return Role.UNRECOGNIZED;
  }
}

export function roleToJSON(object: Role): string {
  switch (object) {
    case Role.ROLE_UNSPECIFIED:
      return "ROLE_UNSPECIFIED";
    case Role.ROLE_USER:
      return "ROLE_USER";
    case Role.ROLE_AGENT:
      return "ROLE_AGENT";
    case Role.UNRECOGNIZED:
    default:
      return "UNRECOGNIZED";
  }
}

/**
 * --8<-- [start:MessageSendConfiguration]
 * Configuration of a send message request.
 */
export interface SendMessageConfiguration {
  /** The output modes that the agent is expected to respond with. */
  acceptedOutputModes: string[];
  /** A configuration of a webhook that can be used to receive updates */
  pushNotification:
    | PushNotificationConfig
    | undefined;
  /**
   * The maximum number of messages to include in the history. if 0, the
   * history will be unlimited.
   */
  historyLength: number;
  /**
   * If true, the message will be blocking until the task is completed. If
   * false, the message will be non-blocking and the task will be returned
   * immediately. It is the caller's responsibility to check for any task
   * updates.
   */
  blocking: boolean;
}

/**
 * --8<-- [start:Task]
 * Task is the core unit of action for A2A. It has a current status
 * and when results are created for the task they are stored in the
 * artifact. If there are multiple turns for a task, these are stored in
 * history.
 */
export interface Task {
  /**
   * Unique identifier (e.g. UUID) for the task, generated by the server for a
   * new task.
   */
  id: string;
  /**
   * Unique identifier (e.g. UUID) for the contextual collection of interactions
   * (tasks and messages). Created by the A2A server.
   */
  contextId: string;
  /** The current status of a Task, including state and a message. */
  status:
    | TaskStatus
    | undefined;
  /** A set of output artifacts for a Task. */
  artifacts: Artifact[];
  /**
   * protolint:disable REPEATED_FIELD_NAMES_PLURALIZED
   * The history of interactions from a task.
   */
  history: Message[];
  /**
   * protolint:enable REPEATED_FIELD_NAMES_PLURALIZED
   * A key/value object to store custom metadata about a task.
   */
  metadata: { [key: string]: any } | undefined;
}

/**
 * --8<-- [start:TaskStatus]
 * A container for the status of a task
 */
export interface TaskStatus {
  /** The current state of this task */
  state: TaskState;
  /** A message associated with the status. */
  update:
    | Message
    | undefined;
  /**
   * Timestamp when the status was recorded.
   * Example: "2023-10-27T10:00:00Z"
   */
  timestamp: Date | undefined;
}

/**
 * --8<-- [start:Part]
 * Part represents a container for a section of communication content.
 * Parts can be purely textual, some sort of file (image, video, etc) or
 * a structured data blob (i.e. JSON).
 */
export interface Part {
  text?: string | undefined;
  file?: FilePart | undefined;
  data?:
    | DataPart
    | undefined;
  /** Optional metadata associated with this part. */
  metadata: { [key: string]: any } | undefined;
}

/**
 * --8<-- [start:FilePart]
 * FilePart represents the different ways files can be provided. If files are
 * small, directly feeding the bytes is supported via file_with_bytes. If the
 * file is large, the agent should read the content as appropriate directly
 * from the file_with_uri source.
 */
export interface FilePart {
  fileWithUri?: string | undefined;
  fileWithBytes?: Uint8Array | undefined;
  mimeType: string;
  name: string;
}

/**
 * --8<-- [start:DataPart]
 * DataPart represents a structured blob. This is most commonly a JSON payload.
 */
export interface DataPart {
  data: { [key: string]: any } | undefined;
}

/**
 * --8<-- [start:Message]
 * Message is one unit of communication between client and server. It is
 * associated with a context and optionally a task. Since the server is
 * responsible for the context definition, it must always provide a context_id
 * in its messages. The client can optionally provide the context_id if it
 * knows the context to associate the message to. Similarly for task_id,
 * except the server decides if a task is created and whether to include the
 * task_id.
 */
export interface Message {
  /**
   * The unique identifier (e.g. UUID)of the message. This is required and
   * created by the message creator.
   */
  messageId: string;
  /**
   * The context id of the message. This is optional and if set, the message
   * will be associated with the given context.
   */
  contextId: string;
  /**
   * The task id of the message. This is optional and if set, the message
   * will be associated with the given task.
   */
  taskId: string;
  /** A role for the message. */
  role: Role;
  /**
   * protolint:disable REPEATED_FIELD_NAMES_PLURALIZED
   * Content is the container of the message content.
   */
  content: Part[];
  /**
   * protolint:enable REPEATED_FIELD_NAMES_PLURALIZED
   * Any optional metadata to provide along with the message.
   */
  metadata:
    | { [key: string]: any }
    | undefined;
  /** The URIs of extensions that are present or contributed to this Message. */
  extensions: string[];
}

/**
 * --8<-- [start:Artifact]
 * Artifacts are the container for task completed results. These are similar
 * to Messages but are intended to be the product of a task, as opposed to
 * point-to-point communication.
 */
export interface Artifact {
  /**
   * Unique identifier (e.g. UUID) for the artifact. It must be at least unique
   * within a task.
   */
  artifactId: string;
  /** A human readable name for the artifact. */
  name: string;
  /** A human readable description of the artifact, optional. */
  description: string;
  /** The content of the artifact. */
  parts: Part[];
  /** Optional metadata included with the artifact. */
  metadata:
    | { [key: string]: any }
    | undefined;
  /** The URIs of extensions that are present or contributed to this Artifact. */
  extensions: string[];
}

/**
 * --8<-- [start:TaskStatusUpdateEvent]
 * TaskStatusUpdateEvent is a delta even on a task indicating that a task
 * has changed.
 */
export interface TaskStatusUpdateEvent {
  /** The id of the task that is changed */
  taskId: string;
  /** The id of the context that the task belongs to */
  contextId: string;
  /** The new status of the task. */
  status:
    | TaskStatus
    | undefined;
  /** Whether this is the last status update expected for this task. */
  final: boolean;
  /** Optional metadata to associate with the task update. */
  metadata: { [key: string]: any } | undefined;
}

/**
 * --8<-- [start:TaskArtifactUpdateEvent]
 * TaskArtifactUpdateEvent represents a task delta where an artifact has
 * been generated.
 */
export interface TaskArtifactUpdateEvent {
  /** The id of the task for this artifact */
  taskId: string;
  /** The id of the context that this task belongs too */
  contextId: string;
  /** The artifact itself */
  artifact:
    | Artifact
    | undefined;
  /** Whether this should be appended to a prior one produced */
  append: boolean;
  /** Whether this represents the last part of an artifact */
  lastChunk: boolean;
  /** Optional metadata associated with the artifact update. */
  metadata: { [key: string]: any } | undefined;
}

/**
 * --8<-- [start:PushNotificationConfig]
 * Configuration for setting up push notifications for task updates.
 */
export interface PushNotificationConfig {
  /** A unique identifier (e.g. UUID) for this push notification. */
  id: string;
  /** Url to send the notification too */
  url: string;
  /** Token unique for this task/session */
  token: string;
  /** Information about the authentication to sent with the notification */
  authentication: AuthenticationInfo | undefined;
}

/**
 * --8<-- [start:PushNotificationAuthenticationInfo]
 * Defines authentication details, used for push notifications.
 */
export interface AuthenticationInfo {
  /** Supported authentication schemes - e.g. Basic, Bearer, etc */
  schemes: string[];
  /** Optional credentials */
  credentials: string;
}

/**
 * --8<-- [start:AgentInterface]
 * Defines additional transport information for the agent.
 */
export interface AgentInterface {
  /** The url this interface is found at. */
  url: string;
  /**
   * The transport supported this url. This is an open form string, to be
   * easily extended for many transport protocols. The core ones officially
   * supported are JSONRPC, GRPC and HTTP+JSON.
   */
  transport: string;
}

/**
 * --8<-- [start:AgentCard]
 * AgentCard conveys key information:
 * - Overall details (version, name, description, uses)
 * - Skills; a set of actions/solutions the agent can perform
 * - Default modalities/content types supported by the agent.
 * - Authentication requirements
 * Next ID: 19
 */
export interface AgentCard {
  /** The version of the A2A protocol this agent supports. */
  protocolVersion: string;
  /**
   * A human readable name for the agent.
   * Example: "Recipe Agent"
   */
  name: string;
  /**
   * A description of the agent's domain of action/solution space.
   * Example: "Agent that helps users with recipes and cooking."
   */
  description: string;
  /**
   * A URL to the address the agent is hosted at. This represents the
   * preferred endpoint as declared by the agent.
   */
  url: string;
  /** The transport of the preferred endpoint. If empty, defaults to JSONRPC. */
  preferredTransport: string;
  /**
   * Announcement of additional supported transports. Client can use any of
   * the supported transports.
   */
  additionalInterfaces: AgentInterface[];
  /** The service provider of the agent. */
  provider:
    | AgentProvider
    | undefined;
  /**
   * The version of the agent.
   * Example: "1.0.0"
   */
  version: string;
  /** A url to provide additional documentation about the agent. */
  documentationUrl: string;
  /** A2A Capability set supported by the agent. */
  capabilities:
    | AgentCapabilities
    | undefined;
  /** The security scheme details used for authenticating with this agent. */
  securitySchemes: { [key: string]: SecurityScheme };
  /**
   * protolint:disable REPEATED_FIELD_NAMES_PLURALIZED
   * Security requirements for contacting the agent.
   * This list can be seen as an OR of ANDs. Each object in the list describes
   * one possible set of security requirements that must be present on a
   * request. This allows specifying, for example, "callers must either use
   * OAuth OR an API Key AND mTLS."
   * Example:
   * security {
   *   schemes { key: "oauth" value { list: ["read"] } }
   * }
   * security {
   *   schemes { key: "api-key" }
   *   schemes { key: "mtls" }
   * }
   */
  security: Security[];
  /**
   * protolint:enable REPEATED_FIELD_NAMES_PLURALIZED
   * The set of interaction modes that the agent supports across all skills.
   * This can be overridden per skill. Defined as mime types.
   */
  defaultInputModes: string[];
  /** The mime types supported as outputs from this agent. */
  defaultOutputModes: string[];
  /**
   * Skills represent a unit of ability an agent can perform. This may
   * somewhat abstract but represents a more focused set of actions that the
   * agent is highly likely to succeed at.
   */
  skills: AgentSkill[];
  /**
   * Whether the agent supports providing an extended agent card when
   * the user is authenticated, i.e. is the card from .well-known
   * different than the card from GetAgentCard.
   */
  supportsAuthenticatedExtendedCard: boolean;
  /** JSON Web Signatures computed for this AgentCard. */
  signatures: AgentCardSignature[];
  /** An optional URL to an icon for the agent. */
  iconUrl: string;
}

export interface AgentCard_SecuritySchemesEntry {
  key: string;
  value: SecurityScheme | undefined;
}

/**
 * --8<-- [start:AgentProvider]
 * Represents information about the service provider of an agent.
 */
export interface AgentProvider {
  /**
   * The providers reference url
   * Example: "https://ai.google.dev"
   */
  url: string;
  /**
   * The providers organization name
   * Example: "Google"
   */
  organization: string;
}

/**
 * --8<-- [start:AgentCapabilities]
 * Defines the A2A feature set supported by the agent
 */
export interface AgentCapabilities {
  /** If the agent will support streaming responses */
  streaming: boolean;
  /** If the agent can send push notifications to the clients webhook */
  pushNotifications: boolean;
  /** Extensions supported by this agent. */
  extensions: AgentExtension[];
}

/**
 * --8<-- [start:AgentExtension]
 * A declaration of an extension supported by an Agent.
 */
export interface AgentExtension {
  /**
   * The URI of the extension.
   * Example: "https://developers.google.com/identity/protocols/oauth2"
   */
  uri: string;
  /**
   * A description of how this agent uses this extension.
   * Example: "Google OAuth 2.0 authentication"
   */
  description: string;
  /**
   * Whether the client must follow specific requirements of the extension.
   * Example: false
   */
  required: boolean;
  /** Optional configuration for the extension. */
  params: { [key: string]: any } | undefined;
}

/**
 * --8<-- [start:AgentSkill]
 * AgentSkill represents a unit of action/solution that the agent can perform.
 * One can think of this as a type of highly reliable solution that an agent
 * can be tasked to provide. Agents have the autonomy to choose how and when
 * to use specific skills, but clients should have confidence that if the
 * skill is defined that unit of action can be reliably performed.
 */
export interface AgentSkill {
  /** Unique identifier of the skill within this agent. */
  id: string;
  /** A human readable name for the skill. */
  name: string;
  /**
   * A human (or llm) readable description of the skill
   * details and behaviors.
   */
  description: string;
  /**
   * A set of tags for the skill to enhance categorization/utilization.
   * Example: ["cooking", "customer support", "billing"]
   */
  tags: string[];
  /**
   * A set of example queries that this skill is designed to address.
   * These examples should help the caller to understand how to craft requests
   * to the agent to achieve specific goals.
   * Example: ["I need a recipe for bread"]
   */
  examples: string[];
  /** Possible input modalities supported. */
  inputModes: string[];
  /** Possible output modalities produced */
  outputModes: string[];
  /**
   * protolint:disable REPEATED_FIELD_NAMES_PLURALIZED
   * Security schemes necessary for the agent to leverage this skill.
   * As in the overall AgentCard.security, this list represents a logical OR of
   * security requirement objects. Each object is a set of security schemes
   * that must be used together (a logical AND).
   */
  security: Security[];
}

/**
 * --8<-- [start:AgentCardSignature]
 * AgentCardSignature represents a JWS signature of an AgentCard.
 * This follows the JSON format of an RFC 7515 JSON Web Signature (JWS).
 */
export interface AgentCardSignature {
  /**
   * The protected JWS header for the signature. This is always a
   * base64url-encoded JSON object. Required.
   */
  protected: string;
  /** The computed signature, base64url-encoded. Required. */
  signature: string;
  /** The unprotected JWS header values. */
  header: { [key: string]: any } | undefined;
}

/** --8<-- [start:TaskPushNotificationConfig] */
export interface TaskPushNotificationConfig {
  /**
   * The resource name of the config.
   * Format: tasks/{task_id}/pushNotificationConfigs/{config_id}
   */
  name: string;
  /** The push notification configuration details. */
  pushNotificationConfig: PushNotificationConfig | undefined;
}

/** protolint:disable REPEATED_FIELD_NAMES_PLURALIZED */
export interface StringList {
  list: string[];
}

export interface Security {
  schemes: { [key: string]: StringList };
}

export interface Security_SchemesEntry {
  key: string;
  value: StringList | undefined;
}

/** --8<-- [start:SecurityScheme] */
export interface SecurityScheme {
  apiKeySecurityScheme?: APIKeySecurityScheme | undefined;
  httpAuthSecurityScheme?: HTTPAuthSecurityScheme | undefined;
  oauth2SecurityScheme?: OAuth2SecurityScheme | undefined;
  openIdConnectSecurityScheme?: OpenIdConnectSecurityScheme | undefined;
  mtlsSecurityScheme?: MutualTlsSecurityScheme | undefined;
}

/** --8<-- [start:APIKeySecurityScheme] */
export interface APIKeySecurityScheme {
  /** Description of this security scheme. */
  description: string;
  /** Location of the API key, valid values are "query", "header", or "cookie" */
  location: string;
  /** Name of the header, query or cookie parameter to be used. */
  name: string;
}

/** --8<-- [start:HTTPAuthSecurityScheme] */
export interface HTTPAuthSecurityScheme {
  /** Description of this security scheme. */
  description: string;
  /**
   * The name of the HTTP Authentication scheme to be used in the
   * Authorization header as defined in RFC7235. The values used SHOULD be
   * registered in the IANA Authentication Scheme registry.
   * The value is case-insensitive, as defined in RFC7235.
   */
  scheme: string;
  /**
   * A hint to the client to identify how the bearer token is formatted.
   * Bearer tokens are usually generated by an authorization server, so
   * this information is primarily for documentation purposes.
   */
  bearerFormat: string;
}

/** --8<-- [start:OAuth2SecurityScheme] */
export interface OAuth2SecurityScheme {
  /** Description of this security scheme. */
  description: string;
  /** An object containing configuration information for the flow types supported */
  flows:
    | OAuthFlows
    | undefined;
  /**
   * URL to the oauth2 authorization server metadata
   * [RFC8414](https://datatracker.ietf.org/doc/html/rfc8414). TLS is required.
   */
  oauth2MetadataUrl: string;
}

/** --8<-- [start:OpenIdConnectSecurityScheme] */
export interface OpenIdConnectSecurityScheme {
  /** Description of this security scheme. */
  description: string;
  /**
   * Well-known URL to discover the [[OpenID-Connect-Discovery]] provider
   * metadata.
   */
  openIdConnectUrl: string;
}

/** --8<-- [start:MutualTLSSecurityScheme] */
export interface MutualTlsSecurityScheme {
  /** Description of this security scheme. */
  description: string;
}

/** --8<-- [start:OAuthFlows] */
export interface OAuthFlows {
  authorizationCode?: AuthorizationCodeOAuthFlow | undefined;
  clientCredentials?: ClientCredentialsOAuthFlow | undefined;
  implicit?: ImplicitOAuthFlow | undefined;
  password?: PasswordOAuthFlow | undefined;
}

/** --8<-- [start:AuthorizationCodeOAuthFlow] */
export interface AuthorizationCodeOAuthFlow {
  /**
   * The authorization URL to be used for this flow. This MUST be in the
   * form of a URL. The OAuth2 standard requires the use of TLS
   */
  authorizationUrl: string;
  /**
   * The token URL to be used for this flow. This MUST be in the form of a URL.
   * The OAuth2 standard requires the use of TLS.
   */
  tokenUrl: string;
  /**
   * The URL to be used for obtaining refresh tokens. This MUST be in the
   * form of a URL. The OAuth2 standard requires the use of TLS.
   */
  refreshUrl: string;
  /**
   * The available scopes for the OAuth2 security scheme. A map between the
   * scope name and a short description for it. The map MAY be empty.
   */
  scopes: { [key: string]: string };
}

export interface AuthorizationCodeOAuthFlow_ScopesEntry {
  key: string;
  value: string;
}

/** --8<-- [start:ClientCredentialsOAuthFlow] */
export interface ClientCredentialsOAuthFlow {
  /**
   * The token URL to be used for this flow. This MUST be in the form of a URL.
   * The OAuth2 standard requires the use of TLS.
   */
  tokenUrl: string;
  /**
   * The URL to be used for obtaining refresh tokens. This MUST be in the
   * form of a URL. The OAuth2 standard requires the use of TLS.
   */
  refreshUrl: string;
  /**
   * The available scopes for the OAuth2 security scheme. A map between the
   * scope name and a short description for it. The map MAY be empty.
   */
  scopes: { [key: string]: string };
}

export interface ClientCredentialsOAuthFlow_ScopesEntry {
  key: string;
  value: string;
}

/** --8<-- [start:ImplicitOAuthFlow] */
export interface ImplicitOAuthFlow {
  /**
   * The authorization URL to be used for this flow. This MUST be in the
   * form of a URL. The OAuth2 standard requires the use of TLS
   */
  authorizationUrl: string;
  /**
   * The URL to be used for obtaining refresh tokens. This MUST be in the
   * form of a URL. The OAuth2 standard requires the use of TLS.
   */
  refreshUrl: string;
  /**
   * The available scopes for the OAuth2 security scheme. A map between the
   * scope name and a short description for it. The map MAY be empty.
   */
  scopes: { [key: string]: string };
}

export interface ImplicitOAuthFlow_ScopesEntry {
  key: string;
  value: string;
}

/** --8<-- [start:PasswordOAuthFlow] */
export interface PasswordOAuthFlow {
  /**
   * The token URL to be used for this flow. This MUST be in the form of a URL.
   * The OAuth2 standard requires the use of TLS.
   */
  tokenUrl: string;
  /**
   * The URL to be used for obtaining refresh tokens. This MUST be in the
   * form of a URL. The OAuth2 standard requires the use of TLS.
   */
  refreshUrl: string;
  /**
   * The available scopes for the OAuth2 security scheme. A map between the
   * scope name and a short description for it. The map MAY be empty.
   */
  scopes: { [key: string]: string };
}

export interface PasswordOAuthFlow_ScopesEntry {
  key: string;
  value: string;
}

/**
 * /////////// Request Messages ///////////
 * --8<-- [start:MessageSendParams]
 */
export interface SendMessageRequest {
  /** The message to send to the agent. */
  request:
    | Message
    | undefined;
  /** Configuration for the send request. */
  configuration:
    | SendMessageConfiguration
    | undefined;
  /** Optional metadata for the request. */
  metadata: { [key: string]: any } | undefined;
}

/** --8<-- [start:GetTaskRequest] */
export interface GetTaskRequest {
  /**
   * The resource name of the task.
   * Format: tasks/{task_id}
   */
  name: string;
  /** The number of most recent messages from the task's history to retrieve. */
  historyLength: number;
}

/** --8<-- [start:CancelTaskRequest] */
export interface CancelTaskRequest {
  /**
   * The resource name of the task to cancel.
   * Format: tasks/{task_id}
   */
  name: string;
}

/** --8<-- [start:GetTaskPushNotificationConfigRequest] */
export interface GetTaskPushNotificationConfigRequest {
  /**
   * The resource name of the config to retrieve.
   * Format: tasks/{task_id}/pushNotificationConfigs/{config_id}
   */
  name: string;
}

/** --8<-- [start:DeleteTaskPushNotificationConfigRequest] */
export interface DeleteTaskPushNotificationConfigRequest {
  /**
   * The resource name of the config to delete.
   * Format: tasks/{task_id}/pushNotificationConfigs/{config_id}
   */
  name: string;
}

/** --8<-- [start:SetTaskPushNotificationConfigRequest] */
export interface CreateTaskPushNotificationConfigRequest {
  /**
   * The parent task resource for this config.
   * Format: tasks/{task_id}
   */
  parent: string;
  /** The ID for the new config. */
  configId: string;
  /** The configuration to create. */
  config: TaskPushNotificationConfig | undefined;
}

/** --8<-- [start:TaskResubscriptionRequest] */
export interface TaskSubscriptionRequest {
  /**
   * The resource name of the task to subscribe to.
   * Format: tasks/{task_id}
   */
  name: string;
}

/** --8<-- [start:ListTaskPushNotificationConfigRequest] */
export interface ListTaskPushNotificationConfigRequest {
  /**
   * The parent task resource.
   * Format: tasks/{task_id}
   */
  parent: string;
  /**
   * For AIP-158 these fields are present. Usually not used/needed.
   * The maximum number of configurations to return.
   * If unspecified, all configs will be returned.
   */
  pageSize: number;
  /**
   * A page token received from a previous
   * ListTaskPushNotificationConfigRequest call.
   * Provide this to retrieve the subsequent page.
   * When paginating, all other parameters provided to
   * `ListTaskPushNotificationConfigRequest` must match the call that provided
   * the page token.
   */
  pageToken: string;
}

/** --8<-- [start:GetAuthenticatedExtendedCardRequest] */
export interface GetAgentCardRequest {
}

/**
 * ////// Response Messages ///////////
 * --8<-- [start:SendMessageSuccessResponse]
 */
export interface SendMessageResponse {
  task?: Task | undefined;
  msg?: Message | undefined;
}

/**
 * --8<-- [start:SendStreamingMessageSuccessResponse]
 * The stream response for a message. The stream should be one of the following
 * sequences:
 * If the response is a message, the stream should contain one, and only one,
 * message and then close
 * If the response is a task lifecycle, the first response should be a Task
 * object followed by zero or more TaskStatusUpdateEvents and
 * TaskArtifactUpdateEvents. The stream should complete when the Task
 * if in an interrupted or terminal state. A stream that ends before these
 * conditions are met are
 */
export interface StreamResponse {
  task?: Task | undefined;
  msg?: Message | undefined;
  statusUpdate?: TaskStatusUpdateEvent | undefined;
  artifactUpdate?: TaskArtifactUpdateEvent | undefined;
}

/** --8<-- [start:ListTaskPushNotificationConfigSuccessResponse] */
export interface ListTaskPushNotificationConfigResponse {
  /** The list of push notification configurations. */
  configs: TaskPushNotificationConfig[];
  /**
   * A token, which can be sent as `page_token` to retrieve the next page.
   * If this field is omitted, there are no subsequent pages.
   */
  nextPageToken: string;
}

function createBaseSendMessageConfiguration(): SendMessageConfiguration {
  return { acceptedOutputModes: [], pushNotification: undefined, historyLength: 0, blocking: false };
}

export const SendMessageConfiguration = {
  encode(message: SendMessageConfiguration, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    for (const v of message.acceptedOutputModes) {
      writer.uint32(10).string(v!);
    }
    if (message.pushNotification !== undefined) {
      PushNotificationConfig.encode(message.pushNotification, writer.uint32(18).fork()).ldelim();
    }
    if (message.historyLength !== 0) {
      writer.uint32(24).int32(message.historyLength);
    }
    if (message.blocking === true) {
      writer.uint32(32).bool(message.blocking);
    }
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): SendMessageConfiguration {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBaseSendMessageConfiguration();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 10) {
            break;
          }

          message.acceptedOutputModes.push(reader.string());
          continue;
        case 2:
          if (tag !== 18) {
            break;
          }

          message.pushNotification = PushNotificationConfig.decode(reader, reader.uint32());
          continue;
        case 3:
          if (tag !== 24) {
            break;
          }

          message.historyLength = reader.int32();
          continue;
        case 4:
          if (tag !== 32) {
            break;
          }

          message.blocking = reader.bool();
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): SendMessageConfiguration {
    return {
      acceptedOutputModes: globalThis.Array.isArray(object?.acceptedOutputModes)
        ? object.acceptedOutputModes.map((e: any) => globalThis.String(e))
        : [],
      pushNotification: isSet(object.pushNotification)
        ? PushNotificationConfig.fromJSON(object.pushNotification)
        : undefined,
      historyLength: isSet(object.historyLength) ? globalThis.Number(object.historyLength) : 0,
      blocking: isSet(object.blocking) ? globalThis.Boolean(object.blocking) : false,
    };
  },

  toJSON(message: SendMessageConfiguration): unknown {
    const obj: any = {};
    if (message.acceptedOutputModes?.length) {
      obj.acceptedOutputModes = message.acceptedOutputModes;
    }
    if (message.pushNotification !== undefined) {
      obj.pushNotification = PushNotificationConfig.toJSON(message.pushNotification);
    }
    if (message.historyLength !== 0) {
      obj.historyLength = Math.round(message.historyLength);
    }
    if (message.blocking === true) {
      obj.blocking = message.blocking;
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<SendMessageConfiguration>, I>>(base?: I): SendMessageConfiguration {
    return SendMessageConfiguration.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<SendMessageConfiguration>, I>>(object: I): SendMessageConfiguration {
    const message = createBaseSendMessageConfiguration();
    message.acceptedOutputModes = object.acceptedOutputModes?.map((e) => e) || [];
    message.pushNotification = (object.pushNotification !== undefined && object.pushNotification !== null)
      ? PushNotificationConfig.fromPartial(object.pushNotification)
      : undefined;
    message.historyLength = object.historyLength ?? 0;
    message.blocking = object.blocking ?? false;
    return message;
  },
};

function createBaseTask(): Task {
  return { id: "", contextId: "", status: undefined, artifacts: [], history: [], metadata: undefined };
}

export const Task = {
  encode(message: Task, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    if (message.id !== "") {
      writer.uint32(10).string(message.id);
    }
    if (message.contextId !== "") {
      writer.uint32(18).string(message.contextId);
    }
    if (message.status !== undefined) {
      TaskStatus.encode(message.status, writer.uint32(26).fork()).ldelim();
    }
    for (const v of message.artifacts) {
      Artifact.encode(v!, writer.uint32(34).fork()).ldelim();
    }
    for (const v of message.history) {
      Message.encode(v!, writer.uint32(42).fork()).ldelim();
    }
    if (message.metadata !== undefined) {
      Struct.encode(Struct.wrap(message.metadata), writer.uint32(50).fork()).ldelim();
    }
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): Task {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBaseTask();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 10) {
            break;
          }

          message.id = reader.string();
          continue;
        case 2:
          if (tag !== 18) {
            break;
          }

          message.contextId = reader.string();
          continue;
        case 3:
          if (tag !== 26) {
            break;
          }

          message.status = TaskStatus.decode(reader, reader.uint32());
          continue;
        case 4:
          if (tag !== 34) {
            break;
          }

          message.artifacts.push(Artifact.decode(reader, reader.uint32()));
          continue;
        case 5:
          if (tag !== 42) {
            break;
          }

          message.history.push(Message.decode(reader, reader.uint32()));
          continue;
        case 6:
          if (tag !== 50) {
            break;
          }

          message.metadata = Struct.unwrap(Struct.decode(reader, reader.uint32()));
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): Task {
    return {
      id: isSet(object.id) ? globalThis.String(object.id) : "",
      contextId: isSet(object.contextId) ? globalThis.String(object.contextId) : "",
      status: isSet(object.status) ? TaskStatus.fromJSON(object.status) : undefined,
      artifacts: globalThis.Array.isArray(object?.artifacts)
        ? object.artifacts.map((e: any) => Artifact.fromJSON(e))
        : [],
      history: globalThis.Array.isArray(object?.history) ? object.history.map((e: any) => Message.fromJSON(e)) : [],
      metadata: isObject(object.metadata) ? object.metadata : undefined,
    };
  },

  toJSON(message: Task): unknown {
    const obj: any = {};
    if (message.id !== "") {
      obj.id = message.id;
    }
    if (message.contextId !== "") {
      obj.contextId = message.contextId;
    }
    if (message.status !== undefined) {
      obj.status = TaskStatus.toJSON(message.status);
    }
    if (message.artifacts?.length) {
      obj.artifacts = message.artifacts.map((e) => Artifact.toJSON(e));
    }
    if (message.history?.length) {
      obj.history = message.history.map((e) => Message.toJSON(e));
    }
    if (message.metadata !== undefined) {
      obj.metadata = message.metadata;
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<Task>, I>>(base?: I): Task {
    return Task.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<Task>, I>>(object: I): Task {
    const message = createBaseTask();
    message.id = object.id ?? "";
    message.contextId = object.contextId ?? "";
    message.status = (object.status !== undefined && object.status !== null)
      ? TaskStatus.fromPartial(object.status)
      : undefined;
    message.artifacts = object.artifacts?.map((e) => Artifact.fromPartial(e)) || [];
    message.history = object.history?.map((e) => Message.fromPartial(e)) || [];
    message.metadata = object.metadata ?? undefined;
    return message;
  },
};

function createBaseTaskStatus(): TaskStatus {
  return { state: 0, update: undefined, timestamp: undefined };
}

export const TaskStatus = {
  encode(message: TaskStatus, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    if (message.state !== 0) {
      writer.uint32(8).int32(message.state);
    }
    if (message.update !== undefined) {
      Message.encode(message.update, writer.uint32(18).fork()).ldelim();
    }
    if (message.timestamp !== undefined) {
      Timestamp.encode(toTimestamp(message.timestamp), writer.uint32(26).fork()).ldelim();
    }
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): TaskStatus {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBaseTaskStatus();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 8) {
            break;
          }

          message.state = reader.int32() as any;
          continue;
        case 2:
          if (tag !== 18) {
            break;
          }

          message.update = Message.decode(reader, reader.uint32());
          continue;
        case 3:
          if (tag !== 26) {
            break;
          }

          message.timestamp = fromTimestamp(Timestamp.decode(reader, reader.uint32()));
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): TaskStatus {
    return {
      state: isSet(object.state) ? taskStateFromJSON(object.state) : 0,
      update: isSet(object.message) ? Message.fromJSON(object.message) : undefined,
      timestamp: isSet(object.timestamp) ? fromJsonTimestamp(object.timestamp) : undefined,
    };
  },

  toJSON(message: TaskStatus): unknown {
    const obj: any = {};
    if (message.state !== 0) {
      obj.state = taskStateToJSON(message.state);
    }
    if (message.update !== undefined) {
      obj.message = Message.toJSON(message.update);
    }
    if (message.timestamp !== undefined) {
      obj.timestamp = message.timestamp.toISOString();
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<TaskStatus>, I>>(base?: I): TaskStatus {
    return TaskStatus.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<TaskStatus>, I>>(object: I): TaskStatus {
    const message = createBaseTaskStatus();
    message.state = object.state ?? 0;
    message.update = (object.update !== undefined && object.update !== null)
      ? Message.fromPartial(object.update)
      : undefined;
    message.timestamp = object.timestamp ?? undefined;
    return message;
  },
};

function createBasePart(): Part {
  return { text: undefined, file: undefined, data: undefined, metadata: undefined };
}

export const Part = {
  encode(message: Part, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    if (message.text !== undefined) {
      writer.uint32(10).string(message.text);
    }
    if (message.file !== undefined) {
      FilePart.encode(message.file, writer.uint32(18).fork()).ldelim();
    }
    if (message.data !== undefined) {
      DataPart.encode(message.data, writer.uint32(26).fork()).ldelim();
    }
    if (message.metadata !== undefined) {
      Struct.encode(Struct.wrap(message.metadata), writer.uint32(34).fork()).ldelim();
    }
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): Part {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBasePart();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 10) {
            break;
          }

          message.text = reader.string();
          continue;
        case 2:
          if (tag !== 18) {
            break;
          }

          message.file = FilePart.decode(reader, reader.uint32());
          continue;
        case 3:
          if (tag !== 26) {
            break;
          }

          message.data = DataPart.decode(reader, reader.uint32());
          continue;
        case 4:
          if (tag !== 34) {
            break;
          }

          message.metadata = Struct.unwrap(Struct.decode(reader, reader.uint32()));
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): Part {
    return {
      text: isSet(object.text) ? globalThis.String(object.text) : undefined,
      file: isSet(object.file) ? FilePart.fromJSON(object.file) : undefined,
      data: isSet(object.data) ? DataPart.fromJSON(object.data) : undefined,
      metadata: isObject(object.metadata) ? object.metadata : undefined,
    };
  },

  toJSON(message: Part): unknown {
    const obj: any = {};
    if (message.text !== undefined) {
      obj.text = message.text;
    }
    if (message.file !== undefined) {
      obj.file = FilePart.toJSON(message.file);
    }
    if (message.data !== undefined) {
      obj.data = DataPart.toJSON(message.data);
    }
    if (message.metadata !== undefined) {
      obj.metadata = message.metadata;
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<Part>, I>>(base?: I): Part {
    return Part.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<Part>, I>>(object: I): Part {
    const message = createBasePart();
    message.text = object.text ?? undefined;
    message.file = (object.file !== undefined && object.file !== null) ? FilePart.fromPartial(object.file) : undefined;
    message.data = (object.data !== undefined && object.data !== null) ? DataPart.fromPartial(object.data) : undefined;
    message.metadata = object.metadata ?? undefined;
    return message;
  },
};

function createBaseFilePart(): FilePart {
  return { fileWithUri: undefined, fileWithBytes: undefined, mimeType: "", name: "" };
}

export const FilePart = {
  encode(message: FilePart, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    if (message.fileWithUri !== undefined) {
      writer.uint32(10).string(message.fileWithUri);
    }
    if (message.fileWithBytes !== undefined) {
      writer.uint32(18).bytes(message.fileWithBytes);
    }
    if (message.mimeType !== "") {
      writer.uint32(26).string(message.mimeType);
    }
    if (message.name !== "") {
      writer.uint32(34).string(message.name);
    }
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): FilePart {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBaseFilePart();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 10) {
            break;
          }

          message.fileWithUri = reader.string();
          continue;
        case 2:
          if (tag !== 18) {
            break;
          }

          message.fileWithBytes = reader.bytes();
          continue;
        case 3:
          if (tag !== 26) {
            break;
          }

          message.mimeType = reader.string();
          continue;
        case 4:
          if (tag !== 34) {
            break;
          }

          message.name = reader.string();
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): FilePart {
    return {
      fileWithUri: isSet(object.fileWithUri) ? globalThis.String(object.fileWithUri) : undefined,
      fileWithBytes: isSet(object.fileWithBytes) ? bytesFromBase64(object.fileWithBytes) : undefined,
      mimeType: isSet(object.mimeType) ? globalThis.String(object.mimeType) : "",
      name: isSet(object.name) ? globalThis.String(object.name) : "",
    };
  },

  toJSON(message: FilePart): unknown {
    const obj: any = {};
    if (message.fileWithUri !== undefined) {
      obj.fileWithUri = message.fileWithUri;
    }
    if (message.fileWithBytes !== undefined) {
      obj.fileWithBytes = base64FromBytes(message.fileWithBytes);
    }
    if (message.mimeType !== "") {
      obj.mimeType = message.mimeType;
    }
    if (message.name !== "") {
      obj.name = message.name;
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<FilePart>, I>>(base?: I): FilePart {
    return FilePart.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<FilePart>, I>>(object: I): FilePart {
    const message = createBaseFilePart();
    message.fileWithUri = object.fileWithUri ?? undefined;
    message.fileWithBytes = object.fileWithBytes ?? undefined;
    message.mimeType = object.mimeType ?? "";
    message.name = object.name ?? "";
    return message;
  },
};

function createBaseDataPart(): DataPart {
  return { data: undefined };
}

export const DataPart = {
  encode(message: DataPart, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    if (message.data !== undefined) {
      Struct.encode(Struct.wrap(message.data), writer.uint32(10).fork()).ldelim();
    }
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): DataPart {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBaseDataPart();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 10) {
            break;
          }

          message.data = Struct.unwrap(Struct.decode(reader, reader.uint32()));
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): DataPart {
    return { data: isObject(object.data) ? object.data : undefined };
  },

  toJSON(message: DataPart): unknown {
    const obj: any = {};
    if (message.data !== undefined) {
      obj.data = message.data;
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<DataPart>, I>>(base?: I): DataPart {
    return DataPart.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<DataPart>, I>>(object: I): DataPart {
    const message = createBaseDataPart();
    message.data = object.data ?? undefined;
    return message;
  },
};

function createBaseMessage(): Message {
  return { messageId: "", contextId: "", taskId: "", role: 0, content: [], metadata: undefined, extensions: [] };
}

export const Message = {
  encode(message: Message, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    if (message.messageId !== "") {
      writer.uint32(10).string(message.messageId);
    }
    if (message.contextId !== "") {
      writer.uint32(18).string(message.contextId);
    }
    if (message.taskId !== "") {
      writer.uint32(26).string(message.taskId);
    }
    if (message.role !== 0) {
      writer.uint32(32).int32(message.role);
    }
    for (const v of message.content) {
      Part.encode(v!, writer.uint32(42).fork()).ldelim();
    }
    if (message.metadata !== undefined) {
      Struct.encode(Struct.wrap(message.metadata), writer.uint32(50).fork()).ldelim();
    }
    for (const v of message.extensions) {
      writer.uint32(58).string(v!);
    }
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): Message {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBaseMessage();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 10) {
            break;
          }

          message.messageId = reader.string();
          continue;
        case 2:
          if (tag !== 18) {
            break;
          }

          message.contextId = reader.string();
          continue;
        case 3:
          if (tag !== 26) {
            break;
          }

          message.taskId = reader.string();
          continue;
        case 4:
          if (tag !== 32) {
            break;
          }

          message.role = reader.int32() as any;
          continue;
        case 5:
          if (tag !== 42) {
            break;
          }

          message.content.push(Part.decode(reader, reader.uint32()));
          continue;
        case 6:
          if (tag !== 50) {
            break;
          }

          message.metadata = Struct.unwrap(Struct.decode(reader, reader.uint32()));
          continue;
        case 7:
          if (tag !== 58) {
            break;
          }

          message.extensions.push(reader.string());
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): Message {
    return {
      messageId: isSet(object.messageId) ? globalThis.String(object.messageId) : "",
      contextId: isSet(object.contextId) ? globalThis.String(object.contextId) : "",
      taskId: isSet(object.taskId) ? globalThis.String(object.taskId) : "",
      role: isSet(object.role) ? roleFromJSON(object.role) : 0,
      content: globalThis.Array.isArray(object?.content) ? object.content.map((e: any) => Part.fromJSON(e)) : [],
      metadata: isObject(object.metadata) ? object.metadata : undefined,
      extensions: globalThis.Array.isArray(object?.extensions)
        ? object.extensions.map((e: any) => globalThis.String(e))
        : [],
    };
  },

  toJSON(message: Message): unknown {
    const obj: any = {};
    if (message.messageId !== "") {
      obj.messageId = message.messageId;
    }
    if (message.contextId !== "") {
      obj.contextId = message.contextId;
    }
    if (message.taskId !== "") {
      obj.taskId = message.taskId;
    }
    if (message.role !== 0) {
      obj.role = roleToJSON(message.role);
    }
    if (message.content?.length) {
      obj.content = message.content.map((e) => Part.toJSON(e));
    }
    if (message.metadata !== undefined) {
      obj.metadata = message.metadata;
    }
    if (message.extensions?.length) {
      obj.extensions = message.extensions;
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<Message>, I>>(base?: I): Message {
    return Message.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<Message>, I>>(object: I): Message {
    const message = createBaseMessage();
    message.messageId = object.messageId ?? "";
    message.contextId = object.contextId ?? "";
    message.taskId = object.taskId ?? "";
    message.role = object.role ?? 0;
    message.content = object.content?.map((e) => Part.fromPartial(e)) || [];
    message.metadata = object.metadata ?? undefined;
    message.extensions = object.extensions?.map((e) => e) || [];
    return message;
  },
};

function createBaseArtifact(): Artifact {
  return { artifactId: "", name: "", description: "", parts: [], metadata: undefined, extensions: [] };
}

export const Artifact = {
  encode(message: Artifact, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    if (message.artifactId !== "") {
      writer.uint32(10).string(message.artifactId);
    }
    if (message.name !== "") {
      writer.uint32(26).string(message.name);
    }
    if (message.description !== "") {
      writer.uint32(34).string(message.description);
    }
    for (const v of message.parts) {
      Part.encode(v!, writer.uint32(42).fork()).ldelim();
    }
    if (message.metadata !== undefined) {
      Struct.encode(Struct.wrap(message.metadata), writer.uint32(50).fork()).ldelim();
    }
    for (const v of message.extensions) {
      writer.uint32(58).string(v!);
    }
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): Artifact {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBaseArtifact();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 10) {
            break;
          }

          message.artifactId = reader.string();
          continue;
        case 3:
          if (tag !== 26) {
            break;
          }

          message.name = reader.string();
          continue;
        case 4:
          if (tag !== 34) {
            break;
          }

          message.description = reader.string();
          continue;
        case 5:
          if (tag !== 42) {
            break;
          }

          message.parts.push(Part.decode(reader, reader.uint32()));
          continue;
        case 6:
          if (tag !== 50) {
            break;
          }

          message.metadata = Struct.unwrap(Struct.decode(reader, reader.uint32()));
          continue;
        case 7:
          if (tag !== 58) {
            break;
          }

          message.extensions.push(reader.string());
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): Artifact {
    return {
      artifactId: isSet(object.artifactId) ? globalThis.String(object.artifactId) : "",
      name: isSet(object.name) ? globalThis.String(object.name) : "",
      description: isSet(object.description) ? globalThis.String(object.description) : "",
      parts: globalThis.Array.isArray(object?.parts) ? object.parts.map((e: any) => Part.fromJSON(e)) : [],
      metadata: isObject(object.metadata) ? object.metadata : undefined,
      extensions: globalThis.Array.isArray(object?.extensions)
        ? object.extensions.map((e: any) => globalThis.String(e))
        : [],
    };
  },

  toJSON(message: Artifact): unknown {
    const obj: any = {};
    if (message.artifactId !== "") {
      obj.artifactId = message.artifactId;
    }
    if (message.name !== "") {
      obj.name = message.name;
    }
    if (message.description !== "") {
      obj.description = message.description;
    }
    if (message.parts?.length) {
      obj.parts = message.parts.map((e) => Part.toJSON(e));
    }
    if (message.metadata !== undefined) {
      obj.metadata = message.metadata;
    }
    if (message.extensions?.length) {
      obj.extensions = message.extensions;
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<Artifact>, I>>(base?: I): Artifact {
    return Artifact.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<Artifact>, I>>(object: I): Artifact {
    const message = createBaseArtifact();
    message.artifactId = object.artifactId ?? "";
    message.name = object.name ?? "";
    message.description = object.description ?? "";
    message.parts = object.parts?.map((e) => Part.fromPartial(e)) || [];
    message.metadata = object.metadata ?? undefined;
    message.extensions = object.extensions?.map((e) => e) || [];
    return message;
  },
};

function createBaseTaskStatusUpdateEvent(): TaskStatusUpdateEvent {
  return { taskId: "", contextId: "", status: undefined, final: false, metadata: undefined };
}

export const TaskStatusUpdateEvent = {
  encode(message: TaskStatusUpdateEvent, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    if (message.taskId !== "") {
      writer.uint32(10).string(message.taskId);
    }
    if (message.contextId !== "") {
      writer.uint32(18).string(message.contextId);
    }
    if (message.status !== undefined) {
      TaskStatus.encode(message.status, writer.uint32(26).fork()).ldelim();
    }
    if (message.final === true) {
      writer.uint32(32).bool(message.final);
    }
    if (message.metadata !== undefined) {
      Struct.encode(Struct.wrap(message.metadata), writer.uint32(42).fork()).ldelim();
    }
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): TaskStatusUpdateEvent {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBaseTaskStatusUpdateEvent();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 10) {
            break;
          }

          message.taskId = reader.string();
          continue;
        case 2:
          if (tag !== 18) {
            break;
          }

          message.contextId = reader.string();
          continue;
        case 3:
          if (tag !== 26) {
            break;
          }

          message.status = TaskStatus.decode(reader, reader.uint32());
          continue;
        case 4:
          if (tag !== 32) {
            break;
          }

          message.final = reader.bool();
          continue;
        case 5:
          if (tag !== 42) {
            break;
          }

          message.metadata = Struct.unwrap(Struct.decode(reader, reader.uint32()));
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): TaskStatusUpdateEvent {
    return {
      taskId: isSet(object.taskId) ? globalThis.String(object.taskId) : "",
      contextId: isSet(object.contextId) ? globalThis.String(object.contextId) : "",
      status: isSet(object.status) ? TaskStatus.fromJSON(object.status) : undefined,
      final: isSet(object.final) ? globalThis.Boolean(object.final) : false,
      metadata: isObject(object.metadata) ? object.metadata : undefined,
    };
  },

  toJSON(message: TaskStatusUpdateEvent): unknown {
    const obj: any = {};
    if (message.taskId !== "") {
      obj.taskId = message.taskId;
    }
    if (message.contextId !== "") {
      obj.contextId = message.contextId;
    }
    if (message.status !== undefined) {
      obj.status = TaskStatus.toJSON(message.status);
    }
    if (message.final === true) {
      obj.final = message.final;
    }
    if (message.metadata !== undefined) {
      obj.metadata = message.metadata;
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<TaskStatusUpdateEvent>, I>>(base?: I): TaskStatusUpdateEvent {
    return TaskStatusUpdateEvent.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<TaskStatusUpdateEvent>, I>>(object: I): TaskStatusUpdateEvent {
    const message = createBaseTaskStatusUpdateEvent();
    message.taskId = object.taskId ?? "";
    message.contextId = object.contextId ?? "";
    message.status = (object.status !== undefined && object.status !== null)
      ? TaskStatus.fromPartial(object.status)
      : undefined;
    message.final = object.final ?? false;
    message.metadata = object.metadata ?? undefined;
    return message;
  },
};

function createBaseTaskArtifactUpdateEvent(): TaskArtifactUpdateEvent {
  return { taskId: "", contextId: "", artifact: undefined, append: false, lastChunk: false, metadata: undefined };
}

export const TaskArtifactUpdateEvent = {
  encode(message: TaskArtifactUpdateEvent, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    if (message.taskId !== "") {
      writer.uint32(10).string(message.taskId);
    }
    if (message.contextId !== "") {
      writer.uint32(18).string(message.contextId);
    }
    if (message.artifact !== undefined) {
      Artifact.encode(message.artifact, writer.uint32(26).fork()).ldelim();
    }
    if (message.append === true) {
      writer.uint32(32).bool(message.append);
    }
    if (message.lastChunk === true) {
      writer.uint32(40).bool(message.lastChunk);
    }
    if (message.metadata !== undefined) {
      Struct.encode(Struct.wrap(message.metadata), writer.uint32(50).fork()).ldelim();
    }
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): TaskArtifactUpdateEvent {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBaseTaskArtifactUpdateEvent();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 10) {
            break;
          }

          message.taskId = reader.string();
          continue;
        case 2:
          if (tag !== 18) {
            break;
          }

          message.contextId = reader.string();
          continue;
        case 3:
          if (tag !== 26) {
            break;
          }

          message.artifact = Artifact.decode(reader, reader.uint32());
          continue;
        case 4:
          if (tag !== 32) {
            break;
          }

          message.append = reader.bool();
          continue;
        case 5:
          if (tag !== 40) {
            break;
          }

          message.lastChunk = reader.bool();
          continue;
        case 6:
          if (tag !== 50) {
            break;
          }

          message.metadata = Struct.unwrap(Struct.decode(reader, reader.uint32()));
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): TaskArtifactUpdateEvent {
    return {
      taskId: isSet(object.taskId) ? globalThis.String(object.taskId) : "",
      contextId: isSet(object.contextId) ? globalThis.String(object.contextId) : "",
      artifact: isSet(object.artifact) ? Artifact.fromJSON(object.artifact) : undefined,
      append: isSet(object.append) ? globalThis.Boolean(object.append) : false,
      lastChunk: isSet(object.lastChunk) ? globalThis.Boolean(object.lastChunk) : false,
      metadata: isObject(object.metadata) ? object.metadata : undefined,
    };
  },

  toJSON(message: TaskArtifactUpdateEvent): unknown {
    const obj: any = {};
    if (message.taskId !== "") {
      obj.taskId = message.taskId;
    }
    if (message.contextId !== "") {
      obj.contextId = message.contextId;
    }
    if (message.artifact !== undefined) {
      obj.artifact = Artifact.toJSON(message.artifact);
    }
    if (message.append === true) {
      obj.append = message.append;
    }
    if (message.lastChunk === true) {
      obj.lastChunk = message.lastChunk;
    }
    if (message.metadata !== undefined) {
      obj.metadata = message.metadata;
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<TaskArtifactUpdateEvent>, I>>(base?: I): TaskArtifactUpdateEvent {
    return TaskArtifactUpdateEvent.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<TaskArtifactUpdateEvent>, I>>(object: I): TaskArtifactUpdateEvent {
    const message = createBaseTaskArtifactUpdateEvent();
    message.taskId = object.taskId ?? "";
    message.contextId = object.contextId ?? "";
    message.artifact = (object.artifact !== undefined && object.artifact !== null)
      ? Artifact.fromPartial(object.artifact)
      : undefined;
    message.append = object.append ?? false;
    message.lastChunk = object.lastChunk ?? false;
    message.metadata = object.metadata ?? undefined;
    return message;
  },
};

function createBasePushNotificationConfig(): PushNotificationConfig {
  return { id: "", url: "", token: "", authentication: undefined };
}

export const PushNotificationConfig = {
  encode(message: PushNotificationConfig, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    if (message.id !== "") {
      writer.uint32(10).string(message.id);
    }
    if (message.url !== "") {
      writer.uint32(18).string(message.url);
    }
    if (message.token !== "") {
      writer.uint32(26).string(message.token);
    }
    if (message.authentication !== undefined) {
      AuthenticationInfo.encode(message.authentication, writer.uint32(34).fork()).ldelim();
    }
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): PushNotificationConfig {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBasePushNotificationConfig();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 10) {
            break;
          }

          message.id = reader.string();
          continue;
        case 2:
          if (tag !== 18) {
            break;
          }

          message.url = reader.string();
          continue;
        case 3:
          if (tag !== 26) {
            break;
          }

          message.token = reader.string();
          continue;
        case 4:
          if (tag !== 34) {
            break;
          }

          message.authentication = AuthenticationInfo.decode(reader, reader.uint32());
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): PushNotificationConfig {
    return {
      id: isSet(object.id) ? globalThis.String(object.id) : "",
      url: isSet(object.url) ? globalThis.String(object.url) : "",
      token: isSet(object.token) ? globalThis.String(object.token) : "",
      authentication: isSet(object.authentication) ? AuthenticationInfo.fromJSON(object.authentication) : undefined,
    };
  },

  toJSON(message: PushNotificationConfig): unknown {
    const obj: any = {};
    if (message.id !== "") {
      obj.id = message.id;
    }
    if (message.url !== "") {
      obj.url = message.url;
    }
    if (message.token !== "") {
      obj.token = message.token;
    }
    if (message.authentication !== undefined) {
      obj.authentication = AuthenticationInfo.toJSON(message.authentication);
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<PushNotificationConfig>, I>>(base?: I): PushNotificationConfig {
    return PushNotificationConfig.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<PushNotificationConfig>, I>>(object: I): PushNotificationConfig {
    const message = createBasePushNotificationConfig();
    message.id = object.id ?? "";
    message.url = object.url ?? "";
    message.token = object.token ?? "";
    message.authentication = (object.authentication !== undefined && object.authentication !== null)
      ? AuthenticationInfo.fromPartial(object.authentication)
      : undefined;
    return message;
  },
};

function createBaseAuthenticationInfo(): AuthenticationInfo {
  return { schemes: [], credentials: "" };
}

export const AuthenticationInfo = {
  encode(message: AuthenticationInfo, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    for (const v of message.schemes) {
      writer.uint32(10).string(v!);
    }
    if (message.credentials !== "") {
      writer.uint32(18).string(message.credentials);
    }
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): AuthenticationInfo {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBaseAuthenticationInfo();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 10) {
            break;
          }

          message.schemes.push(reader.string());
          continue;
        case 2:
          if (tag !== 18) {
            break;
          }

          message.credentials = reader.string();
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): AuthenticationInfo {
    return {
      schemes: globalThis.Array.isArray(object?.schemes) ? object.schemes.map((e: any) => globalThis.String(e)) : [],
      credentials: isSet(object.credentials) ? globalThis.String(object.credentials) : "",
    };
  },

  toJSON(message: AuthenticationInfo): unknown {
    const obj: any = {};
    if (message.schemes?.length) {
      obj.schemes = message.schemes;
    }
    if (message.credentials !== "") {
      obj.credentials = message.credentials;
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<AuthenticationInfo>, I>>(base?: I): AuthenticationInfo {
    return AuthenticationInfo.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<AuthenticationInfo>, I>>(object: I): AuthenticationInfo {
    const message = createBaseAuthenticationInfo();
    message.schemes = object.schemes?.map((e) => e) || [];
    message.credentials = object.credentials ?? "";
    return message;
  },
};

function createBaseAgentInterface(): AgentInterface {
  return { url: "", transport: "" };
}

export const AgentInterface = {
  encode(message: AgentInterface, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    if (message.url !== "") {
      writer.uint32(10).string(message.url);
    }
    if (message.transport !== "") {
      writer.uint32(18).string(message.transport);
    }
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): AgentInterface {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBaseAgentInterface();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 10) {
            break;
          }

          message.url = reader.string();
          continue;
        case 2:
          if (tag !== 18) {
            break;
          }

          message.transport = reader.string();
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): AgentInterface {
    return {
      url: isSet(object.url) ? globalThis.String(object.url) : "",
      transport: isSet(object.transport) ? globalThis.String(object.transport) : "",
    };
  },

  toJSON(message: AgentInterface): unknown {
    const obj: any = {};
    if (message.url !== "") {
      obj.url = message.url;
    }
    if (message.transport !== "") {
      obj.transport = message.transport;
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<AgentInterface>, I>>(base?: I): AgentInterface {
    return AgentInterface.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<AgentInterface>, I>>(object: I): AgentInterface {
    const message = createBaseAgentInterface();
    message.url = object.url ?? "";
    message.transport = object.transport ?? "";
    return message;
  },
};

function createBaseAgentCard(): AgentCard {
  return {
    protocolVersion: "",
    name: "",
    description: "",
    url: "",
    preferredTransport: "",
    additionalInterfaces: [],
    provider: undefined,
    version: "",
    documentationUrl: "",
    capabilities: undefined,
    securitySchemes: {},
    security: [],
    defaultInputModes: [],
    defaultOutputModes: [],
    skills: [],
    supportsAuthenticatedExtendedCard: false,
    signatures: [],
    iconUrl: "",
  };
}

export const AgentCard = {
  encode(message: AgentCard, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    if (message.protocolVersion !== "") {
      writer.uint32(130).string(message.protocolVersion);
    }
    if (message.name !== "") {
      writer.uint32(10).string(message.name);
    }
    if (message.description !== "") {
      writer.uint32(18).string(message.description);
    }
    if (message.url !== "") {
      writer.uint32(26).string(message.url);
    }
    if (message.preferredTransport !== "") {
      writer.uint32(114).string(message.preferredTransport);
    }
    for (const v of message.additionalInterfaces) {
      AgentInterface.encode(v!, writer.uint32(122).fork()).ldelim();
    }
    if (message.provider !== undefined) {
      AgentProvider.encode(message.provider, writer.uint32(34).fork()).ldelim();
    }
    if (message.version !== "") {
      writer.uint32(42).string(message.version);
    }
    if (message.documentationUrl !== "") {
      writer.uint32(50).string(message.documentationUrl);
    }
    if (message.capabilities !== undefined) {
      AgentCapabilities.encode(message.capabilities, writer.uint32(58).fork()).ldelim();
    }
    Object.entries(message.securitySchemes).forEach(([key, value]) => {
      AgentCard_SecuritySchemesEntry.encode({ key: key as any, value }, writer.uint32(66).fork()).ldelim();
    });
    for (const v of message.security) {
      Security.encode(v!, writer.uint32(74).fork()).ldelim();
    }
    for (const v of message.defaultInputModes) {
      writer.uint32(82).string(v!);
    }
    for (const v of message.defaultOutputModes) {
      writer.uint32(90).string(v!);
    }
    for (const v of message.skills) {
      AgentSkill.encode(v!, writer.uint32(98).fork()).ldelim();
    }
    if (message.supportsAuthenticatedExtendedCard === true) {
      writer.uint32(104).bool(message.supportsAuthenticatedExtendedCard);
    }
    for (const v of message.signatures) {
      AgentCardSignature.encode(v!, writer.uint32(138).fork()).ldelim();
    }
    if (message.iconUrl !== "") {
      writer.uint32(146).string(message.iconUrl);
    }
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): AgentCard {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBaseAgentCard();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 16:
          if (tag !== 130) {
            break;
          }

          message.protocolVersion = reader.string();
          continue;
        case 1:
          if (tag !== 10) {
            break;
          }

          message.name = reader.string();
          continue;
        case 2:
          if (tag !== 18) {
            break;
          }

          message.description = reader.string();
          continue;
        case 3:
          if (tag !== 26) {
            break;
          }

          message.url = reader.string();
          continue;
        case 14:
          if (tag !== 114) {
            break;
          }

          message.preferredTransport = reader.string();
          continue;
        case 15:
          if (tag !== 122) {
            break;
          }

          message.additionalInterfaces.push(AgentInterface.decode(reader, reader.uint32()));
          continue;
        case 4:
          if (tag !== 34) {
            break;
          }

          message.provider = AgentProvider.decode(reader, reader.uint32());
          continue;
        case 5:
          if (tag !== 42) {
            break;
          }

          message.version = reader.string();
          continue;
        case 6:
          if (tag !== 50) {
            break;
          }

          message.documentationUrl = reader.string();
          continue;
        case 7:
          if (tag !== 58) {
            break;
          }

          message.capabilities = AgentCapabilities.decode(reader, reader.uint32());
          continue;
        case 8:
          if (tag !== 66) {
            break;
          }

          const entry8 = AgentCard_SecuritySchemesEntry.decode(reader, reader.uint32());
          if (entry8.value !== undefined) {
            message.securitySchemes[entry8.key] = entry8.value;
          }
          continue;
        case 9:
          if (tag !== 74) {
            break;
          }

          message.security.push(Security.decode(reader, reader.uint32()));
          continue;
        case 10:
          if (tag !== 82) {
            break;
          }

          message.defaultInputModes.push(reader.string());
          continue;
        case 11:
          if (tag !== 90) {
            break;
          }

          message.defaultOutputModes.push(reader.string());
          continue;
        case 12:
          if (tag !== 98) {
            break;
          }

          message.skills.push(AgentSkill.decode(reader, reader.uint32()));
          continue;
        case 13:
          if (tag !== 104) {
            break;
          }

          message.supportsAuthenticatedExtendedCard = reader.bool();
          continue;
        case 17:
          if (tag !== 138) {
            break;
          }

          message.signatures.push(AgentCardSignature.decode(reader, reader.uint32()));
          continue;
        case 18:
          if (tag !== 146) {
            break;
          }

          message.iconUrl = reader.string();
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): AgentCard {
    return {
      protocolVersion: isSet(object.protocolVersion) ? globalThis.String(object.protocolVersion) : "",
      name: isSet(object.name) ? globalThis.String(object.name) : "",
      description: isSet(object.description) ? globalThis.String(object.description) : "",
      url: isSet(object.url) ? globalThis.String(object.url) : "",
      preferredTransport: isSet(object.preferredTransport) ? globalThis.String(object.preferredTransport) : "",
      additionalInterfaces: globalThis.Array.isArray(object?.additionalInterfaces)
        ? object.additionalInterfaces.map((e: any) => AgentInterface.fromJSON(e))
        : [],
      provider: isSet(object.provider) ? AgentProvider.fromJSON(object.provider) : undefined,
      version: isSet(object.version) ? globalThis.String(object.version) : "",
      documentationUrl: isSet(object.documentationUrl) ? globalThis.String(object.documentationUrl) : "",
      capabilities: isSet(object.capabilities) ? AgentCapabilities.fromJSON(object.capabilities) : undefined,
      securitySchemes: isObject(object.securitySchemes)
        ? Object.entries(object.securitySchemes).reduce<{ [key: string]: SecurityScheme }>((acc, [key, value]) => {
          acc[key] = SecurityScheme.fromJSON(value);
          return acc;
        }, {})
        : {},
      security: globalThis.Array.isArray(object?.security) ? object.security.map((e: any) => Security.fromJSON(e)) : [],
      defaultInputModes: globalThis.Array.isArray(object?.defaultInputModes)
        ? object.defaultInputModes.map((e: any) => globalThis.String(e))
        : [],
      defaultOutputModes: globalThis.Array.isArray(object?.defaultOutputModes)
        ? object.defaultOutputModes.map((e: any) => globalThis.String(e))
        : [],
      skills: globalThis.Array.isArray(object?.skills) ? object.skills.map((e: any) => AgentSkill.fromJSON(e)) : [],
      supportsAuthenticatedExtendedCard: isSet(object.supportsAuthenticatedExtendedCard)
        ? globalThis.Boolean(object.supportsAuthenticatedExtendedCard)
        : false,
      signatures: globalThis.Array.isArray(object?.signatures)
        ? object.signatures.map((e: any) => AgentCardSignature.fromJSON(e))
        : [],
      iconUrl: isSet(object.iconUrl) ? globalThis.String(object.iconUrl) : "",
    };
  },

  toJSON(message: AgentCard): unknown {
    const obj: any = {};
    if (message.protocolVersion !== "") {
      obj.protocolVersion = message.protocolVersion;
    }
    if (message.name !== "") {
      obj.name = message.name;
    }
    if (message.description !== "") {
      obj.description = message.description;
    }
    if (message.url !== "") {
      obj.url = message.url;
    }
    if (message.preferredTransport !== "") {
      obj.preferredTransport = message.preferredTransport;
    }
    if (message.additionalInterfaces?.length) {
      obj.additionalInterfaces = message.additionalInterfaces.map((e) => AgentInterface.toJSON(e));
    }
    if (message.provider !== undefined) {
      obj.provider = AgentProvider.toJSON(message.provider);
    }
    if (message.version !== "") {
      obj.version = message.version;
    }
    if (message.documentationUrl !== "") {
      obj.documentationUrl = message.documentationUrl;
    }
    if (message.capabilities !== undefined) {
      obj.capabilities = AgentCapabilities.toJSON(message.capabilities);
    }
    if (message.securitySchemes) {
      const entries = Object.entries(message.securitySchemes);
      if (entries.length > 0) {
        obj.securitySchemes = {};
        entries.forEach(([k, v]) => {
          obj.securitySchemes[k] = SecurityScheme.toJSON(v);
        });
      }
    }
    if (message.security?.length) {
      obj.security = message.security.map((e) => Security.toJSON(e));
    }
    if (message.defaultInputModes?.length) {
      obj.defaultInputModes = message.defaultInputModes;
    }
    if (message.defaultOutputModes?.length) {
      obj.defaultOutputModes = message.defaultOutputModes;
    }
    if (message.skills?.length) {
      obj.skills = message.skills.map((e) => AgentSkill.toJSON(e));
    }
    if (message.supportsAuthenticatedExtendedCard === true) {
      obj.supportsAuthenticatedExtendedCard = message.supportsAuthenticatedExtendedCard;
    }
    if (message.signatures?.length) {
      obj.signatures = message.signatures.map((e) => AgentCardSignature.toJSON(e));
    }
    if (message.iconUrl !== "") {
      obj.iconUrl = message.iconUrl;
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<AgentCard>, I>>(base?: I): AgentCard {
    return AgentCard.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<AgentCard>, I>>(object: I): AgentCard {
    const message = createBaseAgentCard();
    message.protocolVersion = object.protocolVersion ?? "";
    message.name = object.name ?? "";
    message.description = object.description ?? "";
    message.url = object.url ?? "";
    message.preferredTransport = object.preferredTransport ?? "";
    message.additionalInterfaces = object.additionalInterfaces?.map((e) => AgentInterface.fromPartial(e)) || [];
    message.provider = (object.provider !== undefined && object.provider !== null)
      ? AgentProvider.fromPartial(object.provider)
      : undefined;
    message.version = object.version ?? "";
    message.documentationUrl = object.documentationUrl ?? "";
    message.capabilities = (object.capabilities !== undefined && object.capabilities !== null)
      ? AgentCapabilities.fromPartial(object.capabilities)
      : undefined;
    message.securitySchemes = Object.entries(object.securitySchemes ?? {}).reduce<{ [key: string]: SecurityScheme }>(
      (acc, [key, value]) => {
        if (value !== undefined) {
          acc[key] = SecurityScheme.fromPartial(value);
        }
        return acc;
      },
      {},
    );
    message.security = object.security?.map((e) => Security.fromPartial(e)) || [];
    message.defaultInputModes = object.defaultInputModes?.map((e) => e) || [];
    message.defaultOutputModes = object.defaultOutputModes?.map((e) => e) || [];
    message.skills = object.skills?.map((e) => AgentSkill.fromPartial(e)) || [];
    message.supportsAuthenticatedExtendedCard = object.supportsAuthenticatedExtendedCard ?? false;
    message.signatures = object.signatures?.map((e) => AgentCardSignature.fromPartial(e)) || [];
    message.iconUrl = object.iconUrl ?? "";
    return message;
  },
};

function createBaseAgentCard_SecuritySchemesEntry(): AgentCard_SecuritySchemesEntry {
  return { key: "", value: undefined };
}

export const AgentCard_SecuritySchemesEntry = {
  encode(message: AgentCard_SecuritySchemesEntry, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    if (message.key !== "") {
      writer.uint32(10).string(message.key);
    }
    if (message.value !== undefined) {
      SecurityScheme.encode(message.value, writer.uint32(18).fork()).ldelim();
    }
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): AgentCard_SecuritySchemesEntry {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBaseAgentCard_SecuritySchemesEntry();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 10) {
            break;
          }

          message.key = reader.string();
          continue;
        case 2:
          if (tag !== 18) {
            break;
          }

          message.value = SecurityScheme.decode(reader, reader.uint32());
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): AgentCard_SecuritySchemesEntry {
    return {
      key: isSet(object.key) ? globalThis.String(object.key) : "",
      value: isSet(object.value) ? SecurityScheme.fromJSON(object.value) : undefined,
    };
  },

  toJSON(message: AgentCard_SecuritySchemesEntry): unknown {
    const obj: any = {};
    if (message.key !== "") {
      obj.key = message.key;
    }
    if (message.value !== undefined) {
      obj.value = SecurityScheme.toJSON(message.value);
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<AgentCard_SecuritySchemesEntry>, I>>(base?: I): AgentCard_SecuritySchemesEntry {
    return AgentCard_SecuritySchemesEntry.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<AgentCard_SecuritySchemesEntry>, I>>(
    object: I,
  ): AgentCard_SecuritySchemesEntry {
    const message = createBaseAgentCard_SecuritySchemesEntry();
    message.key = object.key ?? "";
    message.value = (object.value !== undefined && object.value !== null)
      ? SecurityScheme.fromPartial(object.value)
      : undefined;
    return message;
  },
};

function createBaseAgentProvider(): AgentProvider {
  return { url: "", organization: "" };
}

export const AgentProvider = {
  encode(message: AgentProvider, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    if (message.url !== "") {
      writer.uint32(10).string(message.url);
    }
    if (message.organization !== "") {
      writer.uint32(18).string(message.organization);
    }
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): AgentProvider {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBaseAgentProvider();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 10) {
            break;
          }

          message.url = reader.string();
          continue;
        case 2:
          if (tag !== 18) {
            break;
          }

          message.organization = reader.string();
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): AgentProvider {
    return {
      url: isSet(object.url) ? globalThis.String(object.url) : "",
      organization: isSet(object.organization) ? globalThis.String(object.organization) : "",
    };
  },

  toJSON(message: AgentProvider): unknown {
    const obj: any = {};
    if (message.url !== "") {
      obj.url = message.url;
    }
    if (message.organization !== "") {
      obj.organization = message.organization;
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<AgentProvider>, I>>(base?: I): AgentProvider {
    return AgentProvider.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<AgentProvider>, I>>(object: I): AgentProvider {
    const message = createBaseAgentProvider();
    message.url = object.url ?? "";
    message.organization = object.organization ?? "";
    return message;
  },
};

function createBaseAgentCapabilities(): AgentCapabilities {
  return { streaming: false, pushNotifications: false, extensions: [] };
}

export const AgentCapabilities = {
  encode(message: AgentCapabilities, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    if (message.streaming === true) {
      writer.uint32(8).bool(message.streaming);
    }
    if (message.pushNotifications === true) {
      writer.uint32(16).bool(message.pushNotifications);
    }
    for (const v of message.extensions) {
      AgentExtension.encode(v!, writer.uint32(26).fork()).ldelim();
    }
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): AgentCapabilities {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBaseAgentCapabilities();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 8) {
            break;
          }

          message.streaming = reader.bool();
          continue;
        case 2:
          if (tag !== 16) {
            break;
          }

          message.pushNotifications = reader.bool();
          continue;
        case 3:
          if (tag !== 26) {
            break;
          }

          message.extensions.push(AgentExtension.decode(reader, reader.uint32()));
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): AgentCapabilities {
    return {
      streaming: isSet(object.streaming) ? globalThis.Boolean(object.streaming) : false,
      pushNotifications: isSet(object.pushNotifications) ? globalThis.Boolean(object.pushNotifications) : false,
      extensions: globalThis.Array.isArray(object?.extensions)
        ? object.extensions.map((e: any) => AgentExtension.fromJSON(e))
        : [],
    };
  },

  toJSON(message: AgentCapabilities): unknown {
    const obj: any = {};
    if (message.streaming === true) {
      obj.streaming = message.streaming;
    }
    if (message.pushNotifications === true) {
      obj.pushNotifications = message.pushNotifications;
    }
    if (message.extensions?.length) {
      obj.extensions = message.extensions.map((e) => AgentExtension.toJSON(e));
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<AgentCapabilities>, I>>(base?: I): AgentCapabilities {
    return AgentCapabilities.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<AgentCapabilities>, I>>(object: I): AgentCapabilities {
    const message = createBaseAgentCapabilities();
    message.streaming = object.streaming ?? false;
    message.pushNotifications = object.pushNotifications ?? false;
    message.extensions = object.extensions?.map((e) => AgentExtension.fromPartial(e)) || [];
    return message;
  },
};

function createBaseAgentExtension(): AgentExtension {
  return { uri: "", description: "", required: false, params: undefined };
}

export const AgentExtension = {
  encode(message: AgentExtension, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    if (message.uri !== "") {
      writer.uint32(10).string(message.uri);
    }
    if (message.description !== "") {
      writer.uint32(18).string(message.description);
    }
    if (message.required === true) {
      writer.uint32(24).bool(message.required);
    }
    if (message.params !== undefined) {
      Struct.encode(Struct.wrap(message.params), writer.uint32(34).fork()).ldelim();
    }
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): AgentExtension {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBaseAgentExtension();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 10) {
            break;
          }

          message.uri = reader.string();
          continue;
        case 2:
          if (tag !== 18) {
            break;
          }

          message.description = reader.string();
          continue;
        case 3:
          if (tag !== 24) {
            break;
          }

          message.required = reader.bool();
          continue;
        case 4:
          if (tag !== 34) {
            break;
          }

          message.params = Struct.unwrap(Struct.decode(reader, reader.uint32()));
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): AgentExtension {
    return {
      uri: isSet(object.uri) ? globalThis.String(object.uri) : "",
      description: isSet(object.description) ? globalThis.String(object.description) : "",
      required: isSet(object.required) ? globalThis.Boolean(object.required) : false,
      params: isObject(object.params) ? object.params : undefined,
    };
  },

  toJSON(message: AgentExtension): unknown {
    const obj: any = {};
    if (message.uri !== "") {
      obj.uri = message.uri;
    }
    if (message.description !== "") {
      obj.description = message.description;
    }
    if (message.required === true) {
      obj.required = message.required;
    }
    if (message.params !== undefined) {
      obj.params = message.params;
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<AgentExtension>, I>>(base?: I): AgentExtension {
    return AgentExtension.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<AgentExtension>, I>>(object: I): AgentExtension {
    const message = createBaseAgentExtension();
    message.uri = object.uri ?? "";
    message.description = object.description ?? "";
    message.required = object.required ?? false;
    message.params = object.params ?? undefined;
    return message;
  },
};

function createBaseAgentSkill(): AgentSkill {
  return { id: "", name: "", description: "", tags: [], examples: [], inputModes: [], outputModes: [], security: [] };
}

export const AgentSkill = {
  encode(message: AgentSkill, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    if (message.id !== "") {
      writer.uint32(10).string(message.id);
    }
    if (message.name !== "") {
      writer.uint32(18).string(message.name);
    }
    if (message.description !== "") {
      writer.uint32(26).string(message.description);
    }
    for (const v of message.tags) {
      writer.uint32(34).string(v!);
    }
    for (const v of message.examples) {
      writer.uint32(42).string(v!);
    }
    for (const v of message.inputModes) {
      writer.uint32(50).string(v!);
    }
    for (const v of message.outputModes) {
      writer.uint32(58).string(v!);
    }
    for (const v of message.security) {
      Security.encode(v!, writer.uint32(66).fork()).ldelim();
    }
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): AgentSkill {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBaseAgentSkill();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 10) {
            break;
          }

          message.id = reader.string();
          continue;
        case 2:
          if (tag !== 18) {
            break;
          }

          message.name = reader.string();
          continue;
        case 3:
          if (tag !== 26) {
            break;
          }

          message.description = reader.string();
          continue;
        case 4:
          if (tag !== 34) {
            break;
          }

          message.tags.push(reader.string());
          continue;
        case 5:
          if (tag !== 42) {
            break;
          }

          message.examples.push(reader.string());
          continue;
        case 6:
          if (tag !== 50) {
            break;
          }

          message.inputModes.push(reader.string());
          continue;
        case 7:
          if (tag !== 58) {
            break;
          }

          message.outputModes.push(reader.string());
          continue;
        case 8:
          if (tag !== 66) {
            break;
          }

          message.security.push(Security.decode(reader, reader.uint32()));
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): AgentSkill {
    return {
      id: isSet(object.id) ? globalThis.String(object.id) : "",
      name: isSet(object.name) ? globalThis.String(object.name) : "",
      description: isSet(object.description) ? globalThis.String(object.description) : "",
      tags: globalThis.Array.isArray(object?.tags) ? object.tags.map((e: any) => globalThis.String(e)) : [],
      examples: globalThis.Array.isArray(object?.examples) ? object.examples.map((e: any) => globalThis.String(e)) : [],
      inputModes: globalThis.Array.isArray(object?.inputModes)
        ? object.inputModes.map((e: any) => globalThis.String(e))
        : [],
      outputModes: globalThis.Array.isArray(object?.outputModes)
        ? object.outputModes.map((e: any) => globalThis.String(e))
        : [],
      security: globalThis.Array.isArray(object?.security) ? object.security.map((e: any) => Security.fromJSON(e)) : [],
    };
  },

  toJSON(message: AgentSkill): unknown {
    const obj: any = {};
    if (message.id !== "") {
      obj.id = message.id;
    }
    if (message.name !== "") {
      obj.name = message.name;
    }
    if (message.description !== "") {
      obj.description = message.description;
    }
    if (message.tags?.length) {
      obj.tags = message.tags;
    }
    if (message.examples?.length) {
      obj.examples = message.examples;
    }
    if (message.inputModes?.length) {
      obj.inputModes = message.inputModes;
    }
    if (message.outputModes?.length) {
      obj.outputModes = message.outputModes;
    }
    if (message.security?.length) {
      obj.security = message.security.map((e) => Security.toJSON(e));
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<AgentSkill>, I>>(base?: I): AgentSkill {
    return AgentSkill.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<AgentSkill>, I>>(object: I): AgentSkill {
    const message = createBaseAgentSkill();
    message.id = object.id ?? "";
    message.name = object.name ?? "";
    message.description = object.description ?? "";
    message.tags = object.tags?.map((e) => e) || [];
    message.examples = object.examples?.map((e) => e) || [];
    message.inputModes = object.inputModes?.map((e) => e) || [];
    message.outputModes = object.outputModes?.map((e) => e) || [];
    message.security = object.security?.map((e) => Security.fromPartial(e)) || [];
    return message;
  },
};

function createBaseAgentCardSignature(): AgentCardSignature {
  return { protected: "", signature: "", header: undefined };
}

export const AgentCardSignature = {
  encode(message: AgentCardSignature, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    if (message.protected !== "") {
      writer.uint32(10).string(message.protected);
    }
    if (message.signature !== "") {
      writer.uint32(18).string(message.signature);
    }
    if (message.header !== undefined) {
      Struct.encode(Struct.wrap(message.header), writer.uint32(26).fork()).ldelim();
    }
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): AgentCardSignature {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBaseAgentCardSignature();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 10) {
            break;
          }

          message.protected = reader.string();
          continue;
        case 2:
          if (tag !== 18) {
            break;
          }

          message.signature = reader.string();
          continue;
        case 3:
          if (tag !== 26) {
            break;
          }

          message.header = Struct.unwrap(Struct.decode(reader, reader.uint32()));
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): AgentCardSignature {
    return {
      protected: isSet(object.protected) ? globalThis.String(object.protected) : "",
      signature: isSet(object.signature) ? globalThis.String(object.signature) : "",
      header: isObject(object.header) ? object.header : undefined,
    };
  },

  toJSON(message: AgentCardSignature): unknown {
    const obj: any = {};
    if (message.protected !== "") {
      obj.protected = message.protected;
    }
    if (message.signature !== "") {
      obj.signature = message.signature;
    }
    if (message.header !== undefined) {
      obj.header = message.header;
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<AgentCardSignature>, I>>(base?: I): AgentCardSignature {
    return AgentCardSignature.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<AgentCardSignature>, I>>(object: I): AgentCardSignature {
    const message = createBaseAgentCardSignature();
    message.protected = object.protected ?? "";
    message.signature = object.signature ?? "";
    message.header = object.header ?? undefined;
    return message;
  },
};

function createBaseTaskPushNotificationConfig(): TaskPushNotificationConfig {
  return { name: "", pushNotificationConfig: undefined };
}

export const TaskPushNotificationConfig = {
  encode(message: TaskPushNotificationConfig, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    if (message.name !== "") {
      writer.uint32(10).string(message.name);
    }
    if (message.pushNotificationConfig !== undefined) {
      PushNotificationConfig.encode(message.pushNotificationConfig, writer.uint32(18).fork()).ldelim();
    }
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): TaskPushNotificationConfig {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBaseTaskPushNotificationConfig();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 10) {
            break;
          }

          message.name = reader.string();
          continue;
        case 2:
          if (tag !== 18) {
            break;
          }

          message.pushNotificationConfig = PushNotificationConfig.decode(reader, reader.uint32());
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): TaskPushNotificationConfig {
    return {
      name: isSet(object.name) ? globalThis.String(object.name) : "",
      pushNotificationConfig: isSet(object.pushNotificationConfig)
        ? PushNotificationConfig.fromJSON(object.pushNotificationConfig)
        : undefined,
    };
  },

  toJSON(message: TaskPushNotificationConfig): unknown {
    const obj: any = {};
    if (message.name !== "") {
      obj.name = message.name;
    }
    if (message.pushNotificationConfig !== undefined) {
      obj.pushNotificationConfig = PushNotificationConfig.toJSON(message.pushNotificationConfig);
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<TaskPushNotificationConfig>, I>>(base?: I): TaskPushNotificationConfig {
    return TaskPushNotificationConfig.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<TaskPushNotificationConfig>, I>>(object: I): TaskPushNotificationConfig {
    const message = createBaseTaskPushNotificationConfig();
    message.name = object.name ?? "";
    message.pushNotificationConfig =
      (object.pushNotificationConfig !== undefined && object.pushNotificationConfig !== null)
        ? PushNotificationConfig.fromPartial(object.pushNotificationConfig)
        : undefined;
    return message;
  },
};

function createBaseStringList(): StringList {
  return { list: [] };
}

export const StringList = {
  encode(message: StringList, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    for (const v of message.list) {
      writer.uint32(10).string(v!);
    }
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): StringList {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBaseStringList();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 10) {
            break;
          }

          message.list.push(reader.string());
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): StringList {
    return { list: globalThis.Array.isArray(object?.list) ? object.list.map((e: any) => globalThis.String(e)) : [] };
  },

  toJSON(message: StringList): unknown {
    const obj: any = {};
    if (message.list?.length) {
      obj.list = message.list;
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<StringList>, I>>(base?: I): StringList {
    return StringList.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<StringList>, I>>(object: I): StringList {
    const message = createBaseStringList();
    message.list = object.list?.map((e) => e) || [];
    return message;
  },
};

function createBaseSecurity(): Security {
  return { schemes: {} };
}

export const Security = {
  encode(message: Security, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    Object.entries(message.schemes).forEach(([key, value]) => {
      Security_SchemesEntry.encode({ key: key as any, value }, writer.uint32(10).fork()).ldelim();
    });
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): Security {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBaseSecurity();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 10) {
            break;
          }

          const entry1 = Security_SchemesEntry.decode(reader, reader.uint32());
          if (entry1.value !== undefined) {
            message.schemes[entry1.key] = entry1.value;
          }
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): Security {
    return {
      schemes: isObject(object.schemes)
        ? Object.entries(object.schemes).reduce<{ [key: string]: StringList }>((acc, [key, value]) => {
          acc[key] = StringList.fromJSON(value);
          return acc;
        }, {})
        : {},
    };
  },

  toJSON(message: Security): unknown {
    const obj: any = {};
    if (message.schemes) {
      const entries = Object.entries(message.schemes);
      if (entries.length > 0) {
        obj.schemes = {};
        entries.forEach(([k, v]) => {
          obj.schemes[k] = StringList.toJSON(v);
        });
      }
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<Security>, I>>(base?: I): Security {
    return Security.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<Security>, I>>(object: I): Security {
    const message = createBaseSecurity();
    message.schemes = Object.entries(object.schemes ?? {}).reduce<{ [key: string]: StringList }>(
      (acc, [key, value]) => {
        if (value !== undefined) {
          acc[key] = StringList.fromPartial(value);
        }
        return acc;
      },
      {},
    );
    return message;
  },
};

function createBaseSecurity_SchemesEntry(): Security_SchemesEntry {
  return { key: "", value: undefined };
}

export const Security_SchemesEntry = {
  encode(message: Security_SchemesEntry, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    if (message.key !== "") {
      writer.uint32(10).string(message.key);
    }
    if (message.value !== undefined) {
      StringList.encode(message.value, writer.uint32(18).fork()).ldelim();
    }
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): Security_SchemesEntry {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBaseSecurity_SchemesEntry();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 10) {
            break;
          }

          message.key = reader.string();
          continue;
        case 2:
          if (tag !== 18) {
            break;
          }

          message.value = StringList.decode(reader, reader.uint32());
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): Security_SchemesEntry {
    return {
      key: isSet(object.key) ? globalThis.String(object.key) : "",
      value: isSet(object.value) ? StringList.fromJSON(object.value) : undefined,
    };
  },

  toJSON(message: Security_SchemesEntry): unknown {
    const obj: any = {};
    if (message.key !== "") {
      obj.key = message.key;
    }
    if (message.value !== undefined) {
      obj.value = StringList.toJSON(message.value);
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<Security_SchemesEntry>, I>>(base?: I): Security_SchemesEntry {
    return Security_SchemesEntry.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<Security_SchemesEntry>, I>>(object: I): Security_SchemesEntry {
    const message = createBaseSecurity_SchemesEntry();
    message.key = object.key ?? "";
    message.value = (object.value !== undefined && object.value !== null)
      ? StringList.fromPartial(object.value)
      : undefined;
    return message;
  },
};

function createBaseSecurityScheme(): SecurityScheme {
  return {
    apiKeySecurityScheme: undefined,
    httpAuthSecurityScheme: undefined,
    oauth2SecurityScheme: undefined,
    openIdConnectSecurityScheme: undefined,
    mtlsSecurityScheme: undefined,
  };
}

export const SecurityScheme = {
  encode(message: SecurityScheme, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    if (message.apiKeySecurityScheme !== undefined) {
      APIKeySecurityScheme.encode(message.apiKeySecurityScheme, writer.uint32(10).fork()).ldelim();
    }
    if (message.httpAuthSecurityScheme !== undefined) {
      HTTPAuthSecurityScheme.encode(message.httpAuthSecurityScheme, writer.uint32(18).fork()).ldelim();
    }
    if (message.oauth2SecurityScheme !== undefined) {
      OAuth2SecurityScheme.encode(message.oauth2SecurityScheme, writer.uint32(26).fork()).ldelim();
    }
    if (message.openIdConnectSecurityScheme !== undefined) {
      OpenIdConnectSecurityScheme.encode(message.openIdConnectSecurityScheme, writer.uint32(34).fork()).ldelim();
    }
    if (message.mtlsSecurityScheme !== undefined) {
      MutualTlsSecurityScheme.encode(message.mtlsSecurityScheme, writer.uint32(42).fork()).ldelim();
    }
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): SecurityScheme {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBaseSecurityScheme();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 10) {
            break;
          }

          message.apiKeySecurityScheme = APIKeySecurityScheme.decode(reader, reader.uint32());
          continue;
        case 2:
          if (tag !== 18) {
            break;
          }

          message.httpAuthSecurityScheme = HTTPAuthSecurityScheme.decode(reader, reader.uint32());
          continue;
        case 3:
          if (tag !== 26) {
            break;
          }

          message.oauth2SecurityScheme = OAuth2SecurityScheme.decode(reader, reader.uint32());
          continue;
        case 4:
          if (tag !== 34) {
            break;
          }

          message.openIdConnectSecurityScheme = OpenIdConnectSecurityScheme.decode(reader, reader.uint32());
          continue;
        case 5:
          if (tag !== 42) {
            break;
          }

          message.mtlsSecurityScheme = MutualTlsSecurityScheme.decode(reader, reader.uint32());
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): SecurityScheme {
    return {
      apiKeySecurityScheme: isSet(object.apiKeySecurityScheme)
        ? APIKeySecurityScheme.fromJSON(object.apiKeySecurityScheme)
        : undefined,
      httpAuthSecurityScheme: isSet(object.httpAuthSecurityScheme)
        ? HTTPAuthSecurityScheme.fromJSON(object.httpAuthSecurityScheme)
        : undefined,
      oauth2SecurityScheme: isSet(object.oauth2SecurityScheme)
        ? OAuth2SecurityScheme.fromJSON(object.oauth2SecurityScheme)
        : undefined,
      openIdConnectSecurityScheme: isSet(object.openIdConnectSecurityScheme)
        ? OpenIdConnectSecurityScheme.fromJSON(object.openIdConnectSecurityScheme)
        : undefined,
      mtlsSecurityScheme: isSet(object.mtlsSecurityScheme)
        ? MutualTlsSecurityScheme.fromJSON(object.mtlsSecurityScheme)
        : undefined,
    };
  },

  toJSON(message: SecurityScheme): unknown {
    const obj: any = {};
    if (message.apiKeySecurityScheme !== undefined) {
      obj.apiKeySecurityScheme = APIKeySecurityScheme.toJSON(message.apiKeySecurityScheme);
    }
    if (message.httpAuthSecurityScheme !== undefined) {
      obj.httpAuthSecurityScheme = HTTPAuthSecurityScheme.toJSON(message.httpAuthSecurityScheme);
    }
    if (message.oauth2SecurityScheme !== undefined) {
      obj.oauth2SecurityScheme = OAuth2SecurityScheme.toJSON(message.oauth2SecurityScheme);
    }
    if (message.openIdConnectSecurityScheme !== undefined) {
      obj.openIdConnectSecurityScheme = OpenIdConnectSecurityScheme.toJSON(message.openIdConnectSecurityScheme);
    }
    if (message.mtlsSecurityScheme !== undefined) {
      obj.mtlsSecurityScheme = MutualTlsSecurityScheme.toJSON(message.mtlsSecurityScheme);
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<SecurityScheme>, I>>(base?: I): SecurityScheme {
    return SecurityScheme.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<SecurityScheme>, I>>(object: I): SecurityScheme {
    const message = createBaseSecurityScheme();
    message.apiKeySecurityScheme = (object.apiKeySecurityScheme !== undefined && object.apiKeySecurityScheme !== null)
      ? APIKeySecurityScheme.fromPartial(object.apiKeySecurityScheme)
      : undefined;
    message.httpAuthSecurityScheme =
      (object.httpAuthSecurityScheme !== undefined && object.httpAuthSecurityScheme !== null)
        ? HTTPAuthSecurityScheme.fromPartial(object.httpAuthSecurityScheme)
        : undefined;
    message.oauth2SecurityScheme = (object.oauth2SecurityScheme !== undefined && object.oauth2SecurityScheme !== null)
      ? OAuth2SecurityScheme.fromPartial(object.oauth2SecurityScheme)
      : undefined;
    message.openIdConnectSecurityScheme =
      (object.openIdConnectSecurityScheme !== undefined && object.openIdConnectSecurityScheme !== null)
        ? OpenIdConnectSecurityScheme.fromPartial(object.openIdConnectSecurityScheme)
        : undefined;
    message.mtlsSecurityScheme = (object.mtlsSecurityScheme !== undefined && object.mtlsSecurityScheme !== null)
      ? MutualTlsSecurityScheme.fromPartial(object.mtlsSecurityScheme)
      : undefined;
    return message;
  },
};

function createBaseAPIKeySecurityScheme(): APIKeySecurityScheme {
  return { description: "", location: "", name: "" };
}

export const APIKeySecurityScheme = {
  encode(message: APIKeySecurityScheme, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    if (message.description !== "") {
      writer.uint32(10).string(message.description);
    }
    if (message.location !== "") {
      writer.uint32(18).string(message.location);
    }
    if (message.name !== "") {
      writer.uint32(26).string(message.name);
    }
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): APIKeySecurityScheme {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBaseAPIKeySecurityScheme();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 10) {
            break;
          }

          message.description = reader.string();
          continue;
        case 2:
          if (tag !== 18) {
            break;
          }

          message.location = reader.string();
          continue;
        case 3:
          if (tag !== 26) {
            break;
          }

          message.name = reader.string();
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): APIKeySecurityScheme {
    return {
      description: isSet(object.description) ? globalThis.String(object.description) : "",
      location: isSet(object.location) ? globalThis.String(object.location) : "",
      name: isSet(object.name) ? globalThis.String(object.name) : "",
    };
  },

  toJSON(message: APIKeySecurityScheme): unknown {
    const obj: any = {};
    if (message.description !== "") {
      obj.description = message.description;
    }
    if (message.location !== "") {
      obj.location = message.location;
    }
    if (message.name !== "") {
      obj.name = message.name;
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<APIKeySecurityScheme>, I>>(base?: I): APIKeySecurityScheme {
    return APIKeySecurityScheme.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<APIKeySecurityScheme>, I>>(object: I): APIKeySecurityScheme {
    const message = createBaseAPIKeySecurityScheme();
    message.description = object.description ?? "";
    message.location = object.location ?? "";
    message.name = object.name ?? "";
    return message;
  },
};

function createBaseHTTPAuthSecurityScheme(): HTTPAuthSecurityScheme {
  return { description: "", scheme: "", bearerFormat: "" };
}

export const HTTPAuthSecurityScheme = {
  encode(message: HTTPAuthSecurityScheme, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    if (message.description !== "") {
      writer.uint32(10).string(message.description);
    }
    if (message.scheme !== "") {
      writer.uint32(18).string(message.scheme);
    }
    if (message.bearerFormat !== "") {
      writer.uint32(26).string(message.bearerFormat);
    }
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): HTTPAuthSecurityScheme {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBaseHTTPAuthSecurityScheme();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 10) {
            break;
          }

          message.description = reader.string();
          continue;
        case 2:
          if (tag !== 18) {
            break;
          }

          message.scheme = reader.string();
          continue;
        case 3:
          if (tag !== 26) {
            break;
          }

          message.bearerFormat = reader.string();
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): HTTPAuthSecurityScheme {
    return {
      description: isSet(object.description) ? globalThis.String(object.description) : "",
      scheme: isSet(object.scheme) ? globalThis.String(object.scheme) : "",
      bearerFormat: isSet(object.bearerFormat) ? globalThis.String(object.bearerFormat) : "",
    };
  },

  toJSON(message: HTTPAuthSecurityScheme): unknown {
    const obj: any = {};
    if (message.description !== "") {
      obj.description = message.description;
    }
    if (message.scheme !== "") {
      obj.scheme = message.scheme;
    }
    if (message.bearerFormat !== "") {
      obj.bearerFormat = message.bearerFormat;
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<HTTPAuthSecurityScheme>, I>>(base?: I): HTTPAuthSecurityScheme {
    return HTTPAuthSecurityScheme.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<HTTPAuthSecurityScheme>, I>>(object: I): HTTPAuthSecurityScheme {
    const message = createBaseHTTPAuthSecurityScheme();
    message.description = object.description ?? "";
    message.scheme = object.scheme ?? "";
    message.bearerFormat = object.bearerFormat ?? "";
    return message;
  },
};

function createBaseOAuth2SecurityScheme(): OAuth2SecurityScheme {
  return { description: "", flows: undefined, oauth2MetadataUrl: "" };
}

export const OAuth2SecurityScheme = {
  encode(message: OAuth2SecurityScheme, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    if (message.description !== "") {
      writer.uint32(10).string(message.description);
    }
    if (message.flows !== undefined) {
      OAuthFlows.encode(message.flows, writer.uint32(18).fork()).ldelim();
    }
    if (message.oauth2MetadataUrl !== "") {
      writer.uint32(26).string(message.oauth2MetadataUrl);
    }
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): OAuth2SecurityScheme {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBaseOAuth2SecurityScheme();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 10) {
            break;
          }

          message.description = reader.string();
          continue;
        case 2:
          if (tag !== 18) {
            break;
          }

          message.flows = OAuthFlows.decode(reader, reader.uint32());
          continue;
        case 3:
          if (tag !== 26) {
            break;
          }

          message.oauth2MetadataUrl = reader.string();
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): OAuth2SecurityScheme {
    return {
      description: isSet(object.description) ? globalThis.String(object.description) : "",
      flows: isSet(object.flows) ? OAuthFlows.fromJSON(object.flows) : undefined,
      oauth2MetadataUrl: isSet(object.oauth2MetadataUrl) ? globalThis.String(object.oauth2MetadataUrl) : "",
    };
  },

  toJSON(message: OAuth2SecurityScheme): unknown {
    const obj: any = {};
    if (message.description !== "") {
      obj.description = message.description;
    }
    if (message.flows !== undefined) {
      obj.flows = OAuthFlows.toJSON(message.flows);
    }
    if (message.oauth2MetadataUrl !== "") {
      obj.oauth2MetadataUrl = message.oauth2MetadataUrl;
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<OAuth2SecurityScheme>, I>>(base?: I): OAuth2SecurityScheme {
    return OAuth2SecurityScheme.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<OAuth2SecurityScheme>, I>>(object: I): OAuth2SecurityScheme {
    const message = createBaseOAuth2SecurityScheme();
    message.description = object.description ?? "";
    message.flows = (object.flows !== undefined && object.flows !== null)
      ? OAuthFlows.fromPartial(object.flows)
      : undefined;
    message.oauth2MetadataUrl = object.oauth2MetadataUrl ?? "";
    return message;
  },
};

function createBaseOpenIdConnectSecurityScheme(): OpenIdConnectSecurityScheme {
  return { description: "", openIdConnectUrl: "" };
}

export const OpenIdConnectSecurityScheme = {
  encode(message: OpenIdConnectSecurityScheme, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    if (message.description !== "") {
      writer.uint32(10).string(message.description);
    }
    if (message.openIdConnectUrl !== "") {
      writer.uint32(18).string(message.openIdConnectUrl);
    }
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): OpenIdConnectSecurityScheme {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBaseOpenIdConnectSecurityScheme();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 10) {
            break;
          }

          message.description = reader.string();
          continue;
        case 2:
          if (tag !== 18) {
            break;
          }

          message.openIdConnectUrl = reader.string();
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): OpenIdConnectSecurityScheme {
    return {
      description: isSet(object.description) ? globalThis.String(object.description) : "",
      openIdConnectUrl: isSet(object.openIdConnectUrl) ? globalThis.String(object.openIdConnectUrl) : "",
    };
  },

  toJSON(message: OpenIdConnectSecurityScheme): unknown {
    const obj: any = {};
    if (message.description !== "") {
      obj.description = message.description;
    }
    if (message.openIdConnectUrl !== "") {
      obj.openIdConnectUrl = message.openIdConnectUrl;
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<OpenIdConnectSecurityScheme>, I>>(base?: I): OpenIdConnectSecurityScheme {
    return OpenIdConnectSecurityScheme.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<OpenIdConnectSecurityScheme>, I>>(object: I): OpenIdConnectSecurityScheme {
    const message = createBaseOpenIdConnectSecurityScheme();
    message.description = object.description ?? "";
    message.openIdConnectUrl = object.openIdConnectUrl ?? "";
    return message;
  },
};

function createBaseMutualTlsSecurityScheme(): MutualTlsSecurityScheme {
  return { description: "" };
}

export const MutualTlsSecurityScheme = {
  encode(message: MutualTlsSecurityScheme, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    if (message.description !== "") {
      writer.uint32(10).string(message.description);
    }
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): MutualTlsSecurityScheme {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBaseMutualTlsSecurityScheme();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 10) {
            break;
          }

          message.description = reader.string();
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): MutualTlsSecurityScheme {
    return { description: isSet(object.description) ? globalThis.String(object.description) : "" };
  },

  toJSON(message: MutualTlsSecurityScheme): unknown {
    const obj: any = {};
    if (message.description !== "") {
      obj.description = message.description;
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<MutualTlsSecurityScheme>, I>>(base?: I): MutualTlsSecurityScheme {
    return MutualTlsSecurityScheme.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<MutualTlsSecurityScheme>, I>>(object: I): MutualTlsSecurityScheme {
    const message = createBaseMutualTlsSecurityScheme();
    message.description = object.description ?? "";
    return message;
  },
};

function createBaseOAuthFlows(): OAuthFlows {
  return { authorizationCode: undefined, clientCredentials: undefined, implicit: undefined, password: undefined };
}

export const OAuthFlows = {
  encode(message: OAuthFlows, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    if (message.authorizationCode !== undefined) {
      AuthorizationCodeOAuthFlow.encode(message.authorizationCode, writer.uint32(10).fork()).ldelim();
    }
    if (message.clientCredentials !== undefined) {
      ClientCredentialsOAuthFlow.encode(message.clientCredentials, writer.uint32(18).fork()).ldelim();
    }
    if (message.implicit !== undefined) {
      ImplicitOAuthFlow.encode(message.implicit, writer.uint32(26).fork()).ldelim();
    }
    if (message.password !== undefined) {
      PasswordOAuthFlow.encode(message.password, writer.uint32(34).fork()).ldelim();
    }
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): OAuthFlows {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBaseOAuthFlows();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 10) {
            break;
          }

          message.authorizationCode = AuthorizationCodeOAuthFlow.decode(reader, reader.uint32());
          continue;
        case 2:
          if (tag !== 18) {
            break;
          }

          message.clientCredentials = ClientCredentialsOAuthFlow.decode(reader, reader.uint32());
          continue;
        case 3:
          if (tag !== 26) {
            break;
          }

          message.implicit = ImplicitOAuthFlow.decode(reader, reader.uint32());
          continue;
        case 4:
          if (tag !== 34) {
            break;
          }

          message.password = PasswordOAuthFlow.decode(reader, reader.uint32());
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): OAuthFlows {
    return {
      authorizationCode: isSet(object.authorizationCode)
        ? AuthorizationCodeOAuthFlow.fromJSON(object.authorizationCode)
        : undefined,
      clientCredentials: isSet(object.clientCredentials)
        ? ClientCredentialsOAuthFlow.fromJSON(object.clientCredentials)
        : undefined,
      implicit: isSet(object.implicit) ? ImplicitOAuthFlow.fromJSON(object.implicit) : undefined,
      password: isSet(object.password) ? PasswordOAuthFlow.fromJSON(object.password) : undefined,
    };
  },

  toJSON(message: OAuthFlows): unknown {
    const obj: any = {};
    if (message.authorizationCode !== undefined) {
      obj.authorizationCode = AuthorizationCodeOAuthFlow.toJSON(message.authorizationCode);
    }
    if (message.clientCredentials !== undefined) {
      obj.clientCredentials = ClientCredentialsOAuthFlow.toJSON(message.clientCredentials);
    }
    if (message.implicit !== undefined) {
      obj.implicit = ImplicitOAuthFlow.toJSON(message.implicit);
    }
    if (message.password !== undefined) {
      obj.password = PasswordOAuthFlow.toJSON(message.password);
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<OAuthFlows>, I>>(base?: I): OAuthFlows {
    return OAuthFlows.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<OAuthFlows>, I>>(object: I): OAuthFlows {
    const message = createBaseOAuthFlows();
    message.authorizationCode = (object.authorizationCode !== undefined && object.authorizationCode !== null)
      ? AuthorizationCodeOAuthFlow.fromPartial(object.authorizationCode)
      : undefined;
    message.clientCredentials = (object.clientCredentials !== undefined && object.clientCredentials !== null)
      ? ClientCredentialsOAuthFlow.fromPartial(object.clientCredentials)
      : undefined;
    message.implicit = (object.implicit !== undefined && object.implicit !== null)
      ? ImplicitOAuthFlow.fromPartial(object.implicit)
      : undefined;
    message.password = (object.password !== undefined && object.password !== null)
      ? PasswordOAuthFlow.fromPartial(object.password)
      : undefined;
    return message;
  },
};

function createBaseAuthorizationCodeOAuthFlow(): AuthorizationCodeOAuthFlow {
  return { authorizationUrl: "", tokenUrl: "", refreshUrl: "", scopes: {} };
}

export const AuthorizationCodeOAuthFlow = {
  encode(message: AuthorizationCodeOAuthFlow, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    if (message.authorizationUrl !== "") {
      writer.uint32(10).string(message.authorizationUrl);
    }
    if (message.tokenUrl !== "") {
      writer.uint32(18).string(message.tokenUrl);
    }
    if (message.refreshUrl !== "") {
      writer.uint32(26).string(message.refreshUrl);
    }
    Object.entries(message.scopes).forEach(([key, value]) => {
      AuthorizationCodeOAuthFlow_ScopesEntry.encode({ key: key as any, value }, writer.uint32(34).fork()).ldelim();
    });
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): AuthorizationCodeOAuthFlow {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBaseAuthorizationCodeOAuthFlow();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 10) {
            break;
          }

          message.authorizationUrl = reader.string();
          continue;
        case 2:
          if (tag !== 18) {
            break;
          }

          message.tokenUrl = reader.string();
          continue;
        case 3:
          if (tag !== 26) {
            break;
          }

          message.refreshUrl = reader.string();
          continue;
        case 4:
          if (tag !== 34) {
            break;
          }

          const entry4 = AuthorizationCodeOAuthFlow_ScopesEntry.decode(reader, reader.uint32());
          if (entry4.value !== undefined) {
            message.scopes[entry4.key] = entry4.value;
          }
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): AuthorizationCodeOAuthFlow {
    return {
      authorizationUrl: isSet(object.authorizationUrl) ? globalThis.String(object.authorizationUrl) : "",
      tokenUrl: isSet(object.tokenUrl) ? globalThis.String(object.tokenUrl) : "",
      refreshUrl: isSet(object.refreshUrl) ? globalThis.String(object.refreshUrl) : "",
      scopes: isObject(object.scopes)
        ? Object.entries(object.scopes).reduce<{ [key: string]: string }>((acc, [key, value]) => {
          acc[key] = String(value);
          return acc;
        }, {})
        : {},
    };
  },

  toJSON(message: AuthorizationCodeOAuthFlow): unknown {
    const obj: any = {};
    if (message.authorizationUrl !== "") {
      obj.authorizationUrl = message.authorizationUrl;
    }
    if (message.tokenUrl !== "") {
      obj.tokenUrl = message.tokenUrl;
    }
    if (message.refreshUrl !== "") {
      obj.refreshUrl = message.refreshUrl;
    }
    if (message.scopes) {
      const entries = Object.entries(message.scopes);
      if (entries.length > 0) {
        obj.scopes = {};
        entries.forEach(([k, v]) => {
          obj.scopes[k] = v;
        });
      }
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<AuthorizationCodeOAuthFlow>, I>>(base?: I): AuthorizationCodeOAuthFlow {
    return AuthorizationCodeOAuthFlow.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<AuthorizationCodeOAuthFlow>, I>>(object: I): AuthorizationCodeOAuthFlow {
    const message = createBaseAuthorizationCodeOAuthFlow();
    message.authorizationUrl = object.authorizationUrl ?? "";
    message.tokenUrl = object.tokenUrl ?? "";
    message.refreshUrl = object.refreshUrl ?? "";
    message.scopes = Object.entries(object.scopes ?? {}).reduce<{ [key: string]: string }>((acc, [key, value]) => {
      if (value !== undefined) {
        acc[key] = globalThis.String(value);
      }
      return acc;
    }, {});
    return message;
  },
};

function createBaseAuthorizationCodeOAuthFlow_ScopesEntry(): AuthorizationCodeOAuthFlow_ScopesEntry {
  return { key: "", value: "" };
}

export const AuthorizationCodeOAuthFlow_ScopesEntry = {
  encode(message: AuthorizationCodeOAuthFlow_ScopesEntry, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    if (message.key !== "") {
      writer.uint32(10).string(message.key);
    }
    if (message.value !== "") {
      writer.uint32(18).string(message.value);
    }
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): AuthorizationCodeOAuthFlow_ScopesEntry {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBaseAuthorizationCodeOAuthFlow_ScopesEntry();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 10) {
            break;
          }

          message.key = reader.string();
          continue;
        case 2:
          if (tag !== 18) {
            break;
          }

          message.value = reader.string();
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): AuthorizationCodeOAuthFlow_ScopesEntry {
    return {
      key: isSet(object.key) ? globalThis.String(object.key) : "",
      value: isSet(object.value) ? globalThis.String(object.value) : "",
    };
  },

  toJSON(message: AuthorizationCodeOAuthFlow_ScopesEntry): unknown {
    const obj: any = {};
    if (message.key !== "") {
      obj.key = message.key;
    }
    if (message.value !== "") {
      obj.value = message.value;
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<AuthorizationCodeOAuthFlow_ScopesEntry>, I>>(
    base?: I,
  ): AuthorizationCodeOAuthFlow_ScopesEntry {
    return AuthorizationCodeOAuthFlow_ScopesEntry.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<AuthorizationCodeOAuthFlow_ScopesEntry>, I>>(
    object: I,
  ): AuthorizationCodeOAuthFlow_ScopesEntry {
    const message = createBaseAuthorizationCodeOAuthFlow_ScopesEntry();
    message.key = object.key ?? "";
    message.value = object.value ?? "";
    return message;
  },
};

function createBaseClientCredentialsOAuthFlow(): ClientCredentialsOAuthFlow {
  return { tokenUrl: "", refreshUrl: "", scopes: {} };
}

export const ClientCredentialsOAuthFlow = {
  encode(message: ClientCredentialsOAuthFlow, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    if (message.tokenUrl !== "") {
      writer.uint32(10).string(message.tokenUrl);
    }
    if (message.refreshUrl !== "") {
      writer.uint32(18).string(message.refreshUrl);
    }
    Object.entries(message.scopes).forEach(([key, value]) => {
      ClientCredentialsOAuthFlow_ScopesEntry.encode({ key: key as any, value }, writer.uint32(26).fork()).ldelim();
    });
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): ClientCredentialsOAuthFlow {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBaseClientCredentialsOAuthFlow();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 10) {
            break;
          }

          message.tokenUrl = reader.string();
          continue;
        case 2:
          if (tag !== 18) {
            break;
          }

          message.refreshUrl = reader.string();
          continue;
        case 3:
          if (tag !== 26) {
            break;
          }

          const entry3 = ClientCredentialsOAuthFlow_ScopesEntry.decode(reader, reader.uint32());
          if (entry3.value !== undefined) {
            message.scopes[entry3.key] = entry3.value;
          }
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): ClientCredentialsOAuthFlow {
    return {
      tokenUrl: isSet(object.tokenUrl) ? globalThis.String(object.tokenUrl) : "",
      refreshUrl: isSet(object.refreshUrl) ? globalThis.String(object.refreshUrl) : "",
      scopes: isObject(object.scopes)
        ? Object.entries(object.scopes).reduce<{ [key: string]: string }>((acc, [key, value]) => {
          acc[key] = String(value);
          return acc;
        }, {})
        : {},
    };
  },

  toJSON(message: ClientCredentialsOAuthFlow): unknown {
    const obj: any = {};
    if (message.tokenUrl !== "") {
      obj.tokenUrl = message.tokenUrl;
    }
    if (message.refreshUrl !== "") {
      obj.refreshUrl = message.refreshUrl;
    }
    if (message.scopes) {
      const entries = Object.entries(message.scopes);
      if (entries.length > 0) {
        obj.scopes = {};
        entries.forEach(([k, v]) => {
          obj.scopes[k] = v;
        });
      }
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<ClientCredentialsOAuthFlow>, I>>(base?: I): ClientCredentialsOAuthFlow {
    return ClientCredentialsOAuthFlow.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<ClientCredentialsOAuthFlow>, I>>(object: I): ClientCredentialsOAuthFlow {
    const message = createBaseClientCredentialsOAuthFlow();
    message.tokenUrl = object.tokenUrl ?? "";
    message.refreshUrl = object.refreshUrl ?? "";
    message.scopes = Object.entries(object.scopes ?? {}).reduce<{ [key: string]: string }>((acc, [key, value]) => {
      if (value !== undefined) {
        acc[key] = globalThis.String(value);
      }
      return acc;
    }, {});
    return message;
  },
};

function createBaseClientCredentialsOAuthFlow_ScopesEntry(): ClientCredentialsOAuthFlow_ScopesEntry {
  return { key: "", value: "" };
}

export const ClientCredentialsOAuthFlow_ScopesEntry = {
  encode(message: ClientCredentialsOAuthFlow_ScopesEntry, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    if (message.key !== "") {
      writer.uint32(10).string(message.key);
    }
    if (message.value !== "") {
      writer.uint32(18).string(message.value);
    }
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): ClientCredentialsOAuthFlow_ScopesEntry {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBaseClientCredentialsOAuthFlow_ScopesEntry();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 10) {
            break;
          }

          message.key = reader.string();
          continue;
        case 2:
          if (tag !== 18) {
            break;
          }

          message.value = reader.string();
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): ClientCredentialsOAuthFlow_ScopesEntry {
    return {
      key: isSet(object.key) ? globalThis.String(object.key) : "",
      value: isSet(object.value) ? globalThis.String(object.value) : "",
    };
  },

  toJSON(message: ClientCredentialsOAuthFlow_ScopesEntry): unknown {
    const obj: any = {};
    if (message.key !== "") {
      obj.key = message.key;
    }
    if (message.value !== "") {
      obj.value = message.value;
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<ClientCredentialsOAuthFlow_ScopesEntry>, I>>(
    base?: I,
  ): ClientCredentialsOAuthFlow_ScopesEntry {
    return ClientCredentialsOAuthFlow_ScopesEntry.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<ClientCredentialsOAuthFlow_ScopesEntry>, I>>(
    object: I,
  ): ClientCredentialsOAuthFlow_ScopesEntry {
    const message = createBaseClientCredentialsOAuthFlow_ScopesEntry();
    message.key = object.key ?? "";
    message.value = object.value ?? "";
    return message;
  },
};

function createBaseImplicitOAuthFlow(): ImplicitOAuthFlow {
  return { authorizationUrl: "", refreshUrl: "", scopes: {} };
}

export const ImplicitOAuthFlow = {
  encode(message: ImplicitOAuthFlow, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    if (message.authorizationUrl !== "") {
      writer.uint32(10).string(message.authorizationUrl);
    }
    if (message.refreshUrl !== "") {
      writer.uint32(18).string(message.refreshUrl);
    }
    Object.entries(message.scopes).forEach(([key, value]) => {
      ImplicitOAuthFlow_ScopesEntry.encode({ key: key as any, value }, writer.uint32(26).fork()).ldelim();
    });
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): ImplicitOAuthFlow {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBaseImplicitOAuthFlow();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 10) {
            break;
          }

          message.authorizationUrl = reader.string();
          continue;
        case 2:
          if (tag !== 18) {
            break;
          }

          message.refreshUrl = reader.string();
          continue;
        case 3:
          if (tag !== 26) {
            break;
          }

          const entry3 = ImplicitOAuthFlow_ScopesEntry.decode(reader, reader.uint32());
          if (entry3.value !== undefined) {
            message.scopes[entry3.key] = entry3.value;
          }
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): ImplicitOAuthFlow {
    return {
      authorizationUrl: isSet(object.authorizationUrl) ? globalThis.String(object.authorizationUrl) : "",
      refreshUrl: isSet(object.refreshUrl) ? globalThis.String(object.refreshUrl) : "",
      scopes: isObject(object.scopes)
        ? Object.entries(object.scopes).reduce<{ [key: string]: string }>((acc, [key, value]) => {
          acc[key] = String(value);
          return acc;
        }, {})
        : {},
    };
  },

  toJSON(message: ImplicitOAuthFlow): unknown {
    const obj: any = {};
    if (message.authorizationUrl !== "") {
      obj.authorizationUrl = message.authorizationUrl;
    }
    if (message.refreshUrl !== "") {
      obj.refreshUrl = message.refreshUrl;
    }
    if (message.scopes) {
      const entries = Object.entries(message.scopes);
      if (entries.length > 0) {
        obj.scopes = {};
        entries.forEach(([k, v]) => {
          obj.scopes[k] = v;
        });
      }
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<ImplicitOAuthFlow>, I>>(base?: I): ImplicitOAuthFlow {
    return ImplicitOAuthFlow.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<ImplicitOAuthFlow>, I>>(object: I): ImplicitOAuthFlow {
    const message = createBaseImplicitOAuthFlow();
    message.authorizationUrl = object.authorizationUrl ?? "";
    message.refreshUrl = object.refreshUrl ?? "";
    message.scopes = Object.entries(object.scopes ?? {}).reduce<{ [key: string]: string }>((acc, [key, value]) => {
      if (value !== undefined) {
        acc[key] = globalThis.String(value);
      }
      return acc;
    }, {});
    return message;
  },
};

function createBaseImplicitOAuthFlow_ScopesEntry(): ImplicitOAuthFlow_ScopesEntry {
  return { key: "", value: "" };
}

export const ImplicitOAuthFlow_ScopesEntry = {
  encode(message: ImplicitOAuthFlow_ScopesEntry, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    if (message.key !== "") {
      writer.uint32(10).string(message.key);
    }
    if (message.value !== "") {
      writer.uint32(18).string(message.value);
    }
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): ImplicitOAuthFlow_ScopesEntry {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBaseImplicitOAuthFlow_ScopesEntry();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 10) {
            break;
          }

          message.key = reader.string();
          continue;
        case 2:
          if (tag !== 18) {
            break;
          }

          message.value = reader.string();
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): ImplicitOAuthFlow_ScopesEntry {
    return {
      key: isSet(object.key) ? globalThis.String(object.key) : "",
      value: isSet(object.value) ? globalThis.String(object.value) : "",
    };
  },

  toJSON(message: ImplicitOAuthFlow_ScopesEntry): unknown {
    const obj: any = {};
    if (message.key !== "") {
      obj.key = message.key;
    }
    if (message.value !== "") {
      obj.value = message.value;
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<ImplicitOAuthFlow_ScopesEntry>, I>>(base?: I): ImplicitOAuthFlow_ScopesEntry {
    return ImplicitOAuthFlow_ScopesEntry.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<ImplicitOAuthFlow_ScopesEntry>, I>>(
    object: I,
  ): ImplicitOAuthFlow_ScopesEntry {
    const message = createBaseImplicitOAuthFlow_ScopesEntry();
    message.key = object.key ?? "";
    message.value = object.value ?? "";
    return message;
  },
};

function createBasePasswordOAuthFlow(): PasswordOAuthFlow {
  return { tokenUrl: "", refreshUrl: "", scopes: {} };
}

export const PasswordOAuthFlow = {
  encode(message: PasswordOAuthFlow, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    if (message.tokenUrl !== "") {
      writer.uint32(10).string(message.tokenUrl);
    }
    if (message.refreshUrl !== "") {
      writer.uint32(18).string(message.refreshUrl);
    }
    Object.entries(message.scopes).forEach(([key, value]) => {
      PasswordOAuthFlow_ScopesEntry.encode({ key: key as any, value }, writer.uint32(26).fork()).ldelim();
    });
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): PasswordOAuthFlow {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBasePasswordOAuthFlow();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 10) {
            break;
          }

          message.tokenUrl = reader.string();
          continue;
        case 2:
          if (tag !== 18) {
            break;
          }

          message.refreshUrl = reader.string();
          continue;
        case 3:
          if (tag !== 26) {
            break;
          }

          const entry3 = PasswordOAuthFlow_ScopesEntry.decode(reader, reader.uint32());
          if (entry3.value !== undefined) {
            message.scopes[entry3.key] = entry3.value;
          }
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): PasswordOAuthFlow {
    return {
      tokenUrl: isSet(object.tokenUrl) ? globalThis.String(object.tokenUrl) : "",
      refreshUrl: isSet(object.refreshUrl) ? globalThis.String(object.refreshUrl) : "",
      scopes: isObject(object.scopes)
        ? Object.entries(object.scopes).reduce<{ [key: string]: string }>((acc, [key, value]) => {
          acc[key] = String(value);
          return acc;
        }, {})
        : {},
    };
  },

  toJSON(message: PasswordOAuthFlow): unknown {
    const obj: any = {};
    if (message.tokenUrl !== "") {
      obj.tokenUrl = message.tokenUrl;
    }
    if (message.refreshUrl !== "") {
      obj.refreshUrl = message.refreshUrl;
    }
    if (message.scopes) {
      const entries = Object.entries(message.scopes);
      if (entries.length > 0) {
        obj.scopes = {};
        entries.forEach(([k, v]) => {
          obj.scopes[k] = v;
        });
      }
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<PasswordOAuthFlow>, I>>(base?: I): PasswordOAuthFlow {
    return PasswordOAuthFlow.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<PasswordOAuthFlow>, I>>(object: I): PasswordOAuthFlow {
    const message = createBasePasswordOAuthFlow();
    message.tokenUrl = object.tokenUrl ?? "";
    message.refreshUrl = object.refreshUrl ?? "";
    message.scopes = Object.entries(object.scopes ?? {}).reduce<{ [key: string]: string }>((acc, [key, value]) => {
      if (value !== undefined) {
        acc[key] = globalThis.String(value);
      }
      return acc;
    }, {});
    return message;
  },
};

function createBasePasswordOAuthFlow_ScopesEntry(): PasswordOAuthFlow_ScopesEntry {
  return { key: "", value: "" };
}

export const PasswordOAuthFlow_ScopesEntry = {
  encode(message: PasswordOAuthFlow_ScopesEntry, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    if (message.key !== "") {
      writer.uint32(10).string(message.key);
    }
    if (message.value !== "") {
      writer.uint32(18).string(message.value);
    }
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): PasswordOAuthFlow_ScopesEntry {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBasePasswordOAuthFlow_ScopesEntry();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 10) {
            break;
          }

          message.key = reader.string();
          continue;
        case 2:
          if (tag !== 18) {
            break;
          }

          message.value = reader.string();
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): PasswordOAuthFlow_ScopesEntry {
    return {
      key: isSet(object.key) ? globalThis.String(object.key) : "",
      value: isSet(object.value) ? globalThis.String(object.value) : "",
    };
  },

  toJSON(message: PasswordOAuthFlow_ScopesEntry): unknown {
    const obj: any = {};
    if (message.key !== "") {
      obj.key = message.key;
    }
    if (message.value !== "") {
      obj.value = message.value;
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<PasswordOAuthFlow_ScopesEntry>, I>>(base?: I): PasswordOAuthFlow_ScopesEntry {
    return PasswordOAuthFlow_ScopesEntry.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<PasswordOAuthFlow_ScopesEntry>, I>>(
    object: I,
  ): PasswordOAuthFlow_ScopesEntry {
    const message = createBasePasswordOAuthFlow_ScopesEntry();
    message.key = object.key ?? "";
    message.value = object.value ?? "";
    return message;
  },
};

function createBaseSendMessageRequest(): SendMessageRequest {
  return { request: undefined, configuration: undefined, metadata: undefined };
}

export const SendMessageRequest = {
  encode(message: SendMessageRequest, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    if (message.request !== undefined) {
      Message.encode(message.request, writer.uint32(10).fork()).ldelim();
    }
    if (message.configuration !== undefined) {
      SendMessageConfiguration.encode(message.configuration, writer.uint32(18).fork()).ldelim();
    }
    if (message.metadata !== undefined) {
      Struct.encode(Struct.wrap(message.metadata), writer.uint32(26).fork()).ldelim();
    }
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): SendMessageRequest {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBaseSendMessageRequest();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 10) {
            break;
          }

          message.request = Message.decode(reader, reader.uint32());
          continue;
        case 2:
          if (tag !== 18) {
            break;
          }

          message.configuration = SendMessageConfiguration.decode(reader, reader.uint32());
          continue;
        case 3:
          if (tag !== 26) {
            break;
          }

          message.metadata = Struct.unwrap(Struct.decode(reader, reader.uint32()));
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): SendMessageRequest {
    return {
      request: isSet(object.message) ? Message.fromJSON(object.message) : undefined,
      configuration: isSet(object.configuration) ? SendMessageConfiguration.fromJSON(object.configuration) : undefined,
      metadata: isObject(object.metadata) ? object.metadata : undefined,
    };
  },

  toJSON(message: SendMessageRequest): unknown {
    const obj: any = {};
    if (message.request !== undefined) {
      obj.message = Message.toJSON(message.request);
    }
    if (message.configuration !== undefined) {
      obj.configuration = SendMessageConfiguration.toJSON(message.configuration);
    }
    if (message.metadata !== undefined) {
      obj.metadata = message.metadata;
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<SendMessageRequest>, I>>(base?: I): SendMessageRequest {
    return SendMessageRequest.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<SendMessageRequest>, I>>(object: I): SendMessageRequest {
    const message = createBaseSendMessageRequest();
    message.request = (object.request !== undefined && object.request !== null)
      ? Message.fromPartial(object.request)
      : undefined;
    message.configuration = (object.configuration !== undefined && object.configuration !== null)
      ? SendMessageConfiguration.fromPartial(object.configuration)
      : undefined;
    message.metadata = object.metadata ?? undefined;
    return message;
  },
};

function createBaseGetTaskRequest(): GetTaskRequest {
  return { name: "", historyLength: 0 };
}

export const GetTaskRequest = {
  encode(message: GetTaskRequest, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    if (message.name !== "") {
      writer.uint32(10).string(message.name);
    }
    if (message.historyLength !== 0) {
      writer.uint32(16).int32(message.historyLength);
    }
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): GetTaskRequest {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBaseGetTaskRequest();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 10) {
            break;
          }

          message.name = reader.string();
          continue;
        case 2:
          if (tag !== 16) {
            break;
          }

          message.historyLength = reader.int32();
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): GetTaskRequest {
    return {
      name: isSet(object.name) ? globalThis.String(object.name) : "",
      historyLength: isSet(object.historyLength) ? globalThis.Number(object.historyLength) : 0,
    };
  },

  toJSON(message: GetTaskRequest): unknown {
    const obj: any = {};
    if (message.name !== "") {
      obj.name = message.name;
    }
    if (message.historyLength !== 0) {
      obj.historyLength = Math.round(message.historyLength);
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<GetTaskRequest>, I>>(base?: I): GetTaskRequest {
    return GetTaskRequest.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<GetTaskRequest>, I>>(object: I): GetTaskRequest {
    const message = createBaseGetTaskRequest();
    message.name = object.name ?? "";
    message.historyLength = object.historyLength ?? 0;
    return message;
  },
};

function createBaseCancelTaskRequest(): CancelTaskRequest {
  return { name: "" };
}

export const CancelTaskRequest = {
  encode(message: CancelTaskRequest, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    if (message.name !== "") {
      writer.uint32(10).string(message.name);
    }
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): CancelTaskRequest {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBaseCancelTaskRequest();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 10) {
            break;
          }

          message.name = reader.string();
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): CancelTaskRequest {
    return { name: isSet(object.name) ? globalThis.String(object.name) : "" };
  },

  toJSON(message: CancelTaskRequest): unknown {
    const obj: any = {};
    if (message.name !== "") {
      obj.name = message.name;
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<CancelTaskRequest>, I>>(base?: I): CancelTaskRequest {
    return CancelTaskRequest.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<CancelTaskRequest>, I>>(object: I): CancelTaskRequest {
    const message = createBaseCancelTaskRequest();
    message.name = object.name ?? "";
    return message;
  },
};

function createBaseGetTaskPushNotificationConfigRequest(): GetTaskPushNotificationConfigRequest {
  return { name: "" };
}

export const GetTaskPushNotificationConfigRequest = {
  encode(message: GetTaskPushNotificationConfigRequest, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    if (message.name !== "") {
      writer.uint32(10).string(message.name);
    }
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): GetTaskPushNotificationConfigRequest {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBaseGetTaskPushNotificationConfigRequest();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 10) {
            break;
          }

          message.name = reader.string();
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): GetTaskPushNotificationConfigRequest {
    return { name: isSet(object.name) ? globalThis.String(object.name) : "" };
  },

  toJSON(message: GetTaskPushNotificationConfigRequest): unknown {
    const obj: any = {};
    if (message.name !== "") {
      obj.name = message.name;
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<GetTaskPushNotificationConfigRequest>, I>>(
    base?: I,
  ): GetTaskPushNotificationConfigRequest {
    return GetTaskPushNotificationConfigRequest.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<GetTaskPushNotificationConfigRequest>, I>>(
    object: I,
  ): GetTaskPushNotificationConfigRequest {
    const message = createBaseGetTaskPushNotificationConfigRequest();
    message.name = object.name ?? "";
    return message;
  },
};

function createBaseDeleteTaskPushNotificationConfigRequest(): DeleteTaskPushNotificationConfigRequest {
  return { name: "" };
}

export const DeleteTaskPushNotificationConfigRequest = {
  encode(message: DeleteTaskPushNotificationConfigRequest, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    if (message.name !== "") {
      writer.uint32(10).string(message.name);
    }
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): DeleteTaskPushNotificationConfigRequest {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBaseDeleteTaskPushNotificationConfigRequest();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 10) {
            break;
          }

          message.name = reader.string();
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): DeleteTaskPushNotificationConfigRequest {
    return { name: isSet(object.name) ? globalThis.String(object.name) : "" };
  },

  toJSON(message: DeleteTaskPushNotificationConfigRequest): unknown {
    const obj: any = {};
    if (message.name !== "") {
      obj.name = message.name;
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<DeleteTaskPushNotificationConfigRequest>, I>>(
    base?: I,
  ): DeleteTaskPushNotificationConfigRequest {
    return DeleteTaskPushNotificationConfigRequest.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<DeleteTaskPushNotificationConfigRequest>, I>>(
    object: I,
  ): DeleteTaskPushNotificationConfigRequest {
    const message = createBaseDeleteTaskPushNotificationConfigRequest();
    message.name = object.name ?? "";
    return message;
  },
};

function createBaseCreateTaskPushNotificationConfigRequest(): CreateTaskPushNotificationConfigRequest {
  return { parent: "", configId: "", config: undefined };
}

export const CreateTaskPushNotificationConfigRequest = {
  encode(message: CreateTaskPushNotificationConfigRequest, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    if (message.parent !== "") {
      writer.uint32(10).string(message.parent);
    }
    if (message.configId !== "") {
      writer.uint32(18).string(message.configId);
    }
    if (message.config !== undefined) {
      TaskPushNotificationConfig.encode(message.config, writer.uint32(26).fork()).ldelim();
    }
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): CreateTaskPushNotificationConfigRequest {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBaseCreateTaskPushNotificationConfigRequest();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 10) {
            break;
          }

          message.parent = reader.string();
          continue;
        case 2:
          if (tag !== 18) {
            break;
          }

          message.configId = reader.string();
          continue;
        case 3:
          if (tag !== 26) {
            break;
          }

          message.config = TaskPushNotificationConfig.decode(reader, reader.uint32());
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): CreateTaskPushNotificationConfigRequest {
    return {
      parent: isSet(object.parent) ? globalThis.String(object.parent) : "",
      configId: isSet(object.configId) ? globalThis.String(object.configId) : "",
      config: isSet(object.config) ? TaskPushNotificationConfig.fromJSON(object.config) : undefined,
    };
  },

  toJSON(message: CreateTaskPushNotificationConfigRequest): unknown {
    const obj: any = {};
    if (message.parent !== "") {
      obj.parent = message.parent;
    }
    if (message.configId !== "") {
      obj.configId = message.configId;
    }
    if (message.config !== undefined) {
      obj.config = TaskPushNotificationConfig.toJSON(message.config);
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<CreateTaskPushNotificationConfigRequest>, I>>(
    base?: I,
  ): CreateTaskPushNotificationConfigRequest {
    return CreateTaskPushNotificationConfigRequest.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<CreateTaskPushNotificationConfigRequest>, I>>(
    object: I,
  ): CreateTaskPushNotificationConfigRequest {
    const message = createBaseCreateTaskPushNotificationConfigRequest();
    message.parent = object.parent ?? "";
    message.configId = object.configId ?? "";
    message.config = (object.config !== undefined && object.config !== null)
      ? TaskPushNotificationConfig.fromPartial(object.config)
      : undefined;
    return message;
  },
};

function createBaseTaskSubscriptionRequest(): TaskSubscriptionRequest {
  return { name: "" };
}

export const TaskSubscriptionRequest = {
  encode(message: TaskSubscriptionRequest, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    if (message.name !== "") {
      writer.uint32(10).string(message.name);
    }
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): TaskSubscriptionRequest {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBaseTaskSubscriptionRequest();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 10) {
            break;
          }

          message.name = reader.string();
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): TaskSubscriptionRequest {
    return { name: isSet(object.name) ? globalThis.String(object.name) : "" };
  },

  toJSON(message: TaskSubscriptionRequest): unknown {
    const obj: any = {};
    if (message.name !== "") {
      obj.name = message.name;
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<TaskSubscriptionRequest>, I>>(base?: I): TaskSubscriptionRequest {
    return TaskSubscriptionRequest.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<TaskSubscriptionRequest>, I>>(object: I): TaskSubscriptionRequest {
    const message = createBaseTaskSubscriptionRequest();
    message.name = object.name ?? "";
    return message;
  },
};

function createBaseListTaskPushNotificationConfigRequest(): ListTaskPushNotificationConfigRequest {
  return { parent: "", pageSize: 0, pageToken: "" };
}

export const ListTaskPushNotificationConfigRequest = {
  encode(message: ListTaskPushNotificationConfigRequest, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    if (message.parent !== "") {
      writer.uint32(10).string(message.parent);
    }
    if (message.pageSize !== 0) {
      writer.uint32(16).int32(message.pageSize);
    }
    if (message.pageToken !== "") {
      writer.uint32(26).string(message.pageToken);
    }
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): ListTaskPushNotificationConfigRequest {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBaseListTaskPushNotificationConfigRequest();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 10) {
            break;
          }

          message.parent = reader.string();
          continue;
        case 2:
          if (tag !== 16) {
            break;
          }

          message.pageSize = reader.int32();
          continue;
        case 3:
          if (tag !== 26) {
            break;
          }

          message.pageToken = reader.string();
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): ListTaskPushNotificationConfigRequest {
    return {
      parent: isSet(object.parent) ? globalThis.String(object.parent) : "",
      pageSize: isSet(object.pageSize) ? globalThis.Number(object.pageSize) : 0,
      pageToken: isSet(object.pageToken) ? globalThis.String(object.pageToken) : "",
    };
  },

  toJSON(message: ListTaskPushNotificationConfigRequest): unknown {
    const obj: any = {};
    if (message.parent !== "") {
      obj.parent = message.parent;
    }
    if (message.pageSize !== 0) {
      obj.pageSize = Math.round(message.pageSize);
    }
    if (message.pageToken !== "") {
      obj.pageToken = message.pageToken;
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<ListTaskPushNotificationConfigRequest>, I>>(
    base?: I,
  ): ListTaskPushNotificationConfigRequest {
    return ListTaskPushNotificationConfigRequest.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<ListTaskPushNotificationConfigRequest>, I>>(
    object: I,
  ): ListTaskPushNotificationConfigRequest {
    const message = createBaseListTaskPushNotificationConfigRequest();
    message.parent = object.parent ?? "";
    message.pageSize = object.pageSize ?? 0;
    message.pageToken = object.pageToken ?? "";
    return message;
  },
};

function createBaseGetAgentCardRequest(): GetAgentCardRequest {
  return {};
}

export const GetAgentCardRequest = {
  encode(_: GetAgentCardRequest, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): GetAgentCardRequest {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBaseGetAgentCardRequest();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(_: any): GetAgentCardRequest {
    return {};
  },

  toJSON(_: GetAgentCardRequest): unknown {
    const obj: any = {};
    return obj;
  },

  create<I extends Exact<DeepPartial<GetAgentCardRequest>, I>>(base?: I): GetAgentCardRequest {
    return GetAgentCardRequest.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<GetAgentCardRequest>, I>>(_: I): GetAgentCardRequest {
    const message = createBaseGetAgentCardRequest();
    return message;
  },
};

function createBaseSendMessageResponse(): SendMessageResponse {
  return { task: undefined, msg: undefined };
}

export const SendMessageResponse = {
  encode(message: SendMessageResponse, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    if (message.task !== undefined) {
      Task.encode(message.task, writer.uint32(10).fork()).ldelim();
    }
    if (message.msg !== undefined) {
      Message.encode(message.msg, writer.uint32(18).fork()).ldelim();
    }
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): SendMessageResponse {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBaseSendMessageResponse();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 10) {
            break;
          }

          message.task = Task.decode(reader, reader.uint32());
          continue;
        case 2:
          if (tag !== 18) {
            break;
          }

          message.msg = Message.decode(reader, reader.uint32());
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): SendMessageResponse {
    return {
      task: isSet(object.task) ? Task.fromJSON(object.task) : undefined,
      msg: isSet(object.message) ? Message.fromJSON(object.message) : undefined,
    };
  },

  toJSON(message: SendMessageResponse): unknown {
    const obj: any = {};
    if (message.task !== undefined) {
      obj.task = Task.toJSON(message.task);
    }
    if (message.msg !== undefined) {
      obj.message = Message.toJSON(message.msg);
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<SendMessageResponse>, I>>(base?: I): SendMessageResponse {
    return SendMessageResponse.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<SendMessageResponse>, I>>(object: I): SendMessageResponse {
    const message = createBaseSendMessageResponse();
    message.task = (object.task !== undefined && object.task !== null) ? Task.fromPartial(object.task) : undefined;
    message.msg = (object.msg !== undefined && object.msg !== null) ? Message.fromPartial(object.msg) : undefined;
    return message;
  },
};

function createBaseStreamResponse(): StreamResponse {
  return { task: undefined, msg: undefined, statusUpdate: undefined, artifactUpdate: undefined };
}

export const StreamResponse = {
  encode(message: StreamResponse, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    if (message.task !== undefined) {
      Task.encode(message.task, writer.uint32(10).fork()).ldelim();
    }
    if (message.msg !== undefined) {
      Message.encode(message.msg, writer.uint32(18).fork()).ldelim();
    }
    if (message.statusUpdate !== undefined) {
      TaskStatusUpdateEvent.encode(message.statusUpdate, writer.uint32(26).fork()).ldelim();
    }
    if (message.artifactUpdate !== undefined) {
      TaskArtifactUpdateEvent.encode(message.artifactUpdate, writer.uint32(34).fork()).ldelim();
    }
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): StreamResponse {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBaseStreamResponse();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 10) {
            break;
          }

          message.task = Task.decode(reader, reader.uint32());
          continue;
        case 2:
          if (tag !== 18) {
            break;
          }

          message.msg = Message.decode(reader, reader.uint32());
          continue;
        case 3:
          if (tag !== 26) {
            break;
          }

          message.statusUpdate = TaskStatusUpdateEvent.decode(reader, reader.uint32());
          continue;
        case 4:
          if (tag !== 34) {
            break;
          }

          message.artifactUpdate = TaskArtifactUpdateEvent.decode(reader, reader.uint32());
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): StreamResponse {
    return {
      task: isSet(object.task) ? Task.fromJSON(object.task) : undefined,
      msg: isSet(object.message) ? Message.fromJSON(object.message) : undefined,
      statusUpdate: isSet(object.statusUpdate) ? TaskStatusUpdateEvent.fromJSON(object.statusUpdate) : undefined,
      artifactUpdate: isSet(object.artifactUpdate)
        ? TaskArtifactUpdateEvent.fromJSON(object.artifactUpdate)
        : undefined,
    };
  },

  toJSON(message: StreamResponse): unknown {
    const obj: any = {};
    if (message.task !== undefined) {
      obj.task = Task.toJSON(message.task);
    }
    if (message.msg !== undefined) {
      obj.message = Message.toJSON(message.msg);
    }
    if (message.statusUpdate !== undefined) {
      obj.statusUpdate = TaskStatusUpdateEvent.toJSON(message.statusUpdate);
    }
    if (message.artifactUpdate !== undefined) {
      obj.artifactUpdate = TaskArtifactUpdateEvent.toJSON(message.artifactUpdate);
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<StreamResponse>, I>>(base?: I): StreamResponse {
    return StreamResponse.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<StreamResponse>, I>>(object: I): StreamResponse {
    const message = createBaseStreamResponse();
    message.task = (object.task !== undefined && object.task !== null) ? Task.fromPartial(object.task) : undefined;
    message.msg = (object.msg !== undefined && object.msg !== null) ? Message.fromPartial(object.msg) : undefined;
    message.statusUpdate = (object.statusUpdate !== undefined && object.statusUpdate !== null)
      ? TaskStatusUpdateEvent.fromPartial(object.statusUpdate)
      : undefined;
    message.artifactUpdate = (object.artifactUpdate !== undefined && object.artifactUpdate !== null)
      ? TaskArtifactUpdateEvent.fromPartial(object.artifactUpdate)
      : undefined;
    return message;
  },
};

function createBaseListTaskPushNotificationConfigResponse(): ListTaskPushNotificationConfigResponse {
  return { configs: [], nextPageToken: "" };
}

export const ListTaskPushNotificationConfigResponse = {
  encode(message: ListTaskPushNotificationConfigResponse, writer: _m0.Writer = _m0.Writer.create()): _m0.Writer {
    for (const v of message.configs) {
      TaskPushNotificationConfig.encode(v!, writer.uint32(10).fork()).ldelim();
    }
    if (message.nextPageToken !== "") {
      writer.uint32(18).string(message.nextPageToken);
    }
    return writer;
  },

  decode(input: _m0.Reader | Uint8Array, length?: number): ListTaskPushNotificationConfigResponse {
    const reader = input instanceof _m0.Reader ? input : _m0.Reader.create(input);
    let end = length === undefined ? reader.len : reader.pos + length;
    const message = createBaseListTaskPushNotificationConfigResponse();
    while (reader.pos < end) {
      const tag = reader.uint32();
      switch (tag >>> 3) {
        case 1:
          if (tag !== 10) {
            break;
          }

          message.configs.push(TaskPushNotificationConfig.decode(reader, reader.uint32()));
          continue;
        case 2:
          if (tag !== 18) {
            break;
          }

          message.nextPageToken = reader.string();
          continue;
      }
      if ((tag & 7) === 4 || tag === 0) {
        break;
      }
      reader.skipType(tag & 7);
    }
    return message;
  },

  fromJSON(object: any): ListTaskPushNotificationConfigResponse {
    return {
      configs: globalThis.Array.isArray(object?.configs)
        ? object.configs.map((e: any) => TaskPushNotificationConfig.fromJSON(e))
        : [],
      nextPageToken: isSet(object.nextPageToken) ? globalThis.String(object.nextPageToken) : "",
    };
  },

  toJSON(message: ListTaskPushNotificationConfigResponse): unknown {
    const obj: any = {};
    if (message.configs?.length) {
      obj.configs = message.configs.map((e) => TaskPushNotificationConfig.toJSON(e));
    }
    if (message.nextPageToken !== "") {
      obj.nextPageToken = message.nextPageToken;
    }
    return obj;
  },

  create<I extends Exact<DeepPartial<ListTaskPushNotificationConfigResponse>, I>>(
    base?: I,
  ): ListTaskPushNotificationConfigResponse {
    return ListTaskPushNotificationConfigResponse.fromPartial(base ?? ({} as any));
  },
  fromPartial<I extends Exact<DeepPartial<ListTaskPushNotificationConfigResponse>, I>>(
    object: I,
  ): ListTaskPushNotificationConfigResponse {
    const message = createBaseListTaskPushNotificationConfigResponse();
    message.configs = object.configs?.map((e) => TaskPushNotificationConfig.fromPartial(e)) || [];
    message.nextPageToken = object.nextPageToken ?? "";
    return message;
  },
};

/**
 * A2AService defines the gRPC version of the A2A protocol. This has a slightly
 * different shape than the JSONRPC version to better conform to AIP-127,
 * where appropriate. The nouns are AgentCard, Message, Task and
 * TaskPushNotificationConfig.
 * - Messages are not a standard resource so there is no get/delete/update/list
 *   interface, only a send and stream custom methods.
 * - Tasks have a get interface and custom cancel and subscribe methods.
 * - TaskPushNotificationConfig are a resource whose parent is a task.
 *   They have get, list and create methods.
 * - AgentCard is a static resource with only a get method.
 */
export interface A2AService {
  /**
   * Send a message to the agent. This is a blocking call that will return the
   * task once it is completed, or a LRO if requested.
   */
  SendMessage(request: SendMessageRequest): Promise<SendMessageResponse>;
  /**
   * SendStreamingMessage is a streaming call that will return a stream of
   * task update events until the Task is in an interrupted or terminal state.
   */
  SendStreamingMessage(request: SendMessageRequest): Observable<StreamResponse>;
  /** Get the current state of a task from the agent. */
  GetTask(request: GetTaskRequest): Promise<Task>;
  /**
   * Cancel a task from the agent. If supported one should expect no
   * more task updates for the task.
   */
  CancelTask(request: CancelTaskRequest): Promise<Task>;
  /**
   * TaskSubscription is a streaming call that will return a stream of task
   * update events. This attaches the stream to an existing in process task.
   * If the task is complete the stream will return the completed task (like
   * GetTask) and close the stream.
   */
  TaskSubscription(request: TaskSubscriptionRequest): Observable<StreamResponse>;
  /** Set a push notification config for a task. */
  CreateTaskPushNotificationConfig(
    request: CreateTaskPushNotificationConfigRequest,
  ): Promise<TaskPushNotificationConfig>;
  /** Get a push notification config for a task. */
  GetTaskPushNotificationConfig(request: GetTaskPushNotificationConfigRequest): Promise<TaskPushNotificationConfig>;
  /** Get a list of push notifications configured for a task. */
  ListTaskPushNotificationConfig(
    request: ListTaskPushNotificationConfigRequest,
  ): Promise<ListTaskPushNotificationConfigResponse>;
  /** GetAgentCard returns the agent card for the agent. */
  GetAgentCard(request: GetAgentCardRequest): Promise<AgentCard>;
  /** Delete a push notification config for a task. */
  DeleteTaskPushNotificationConfig(request: DeleteTaskPushNotificationConfigRequest): Promise<Empty>;
}

export const A2AServiceServiceName = "a2a.v1.A2AService";
export class A2AServiceClientImpl implements A2AService {
  private readonly rpc: Rpc;
  private readonly service: string;
  constructor(rpc: Rpc, opts?: { service?: string }) {
    this.service = opts?.service || A2AServiceServiceName;
    this.rpc = rpc;
    this.SendMessage = this.SendMessage.bind(this);
    this.SendStreamingMessage = this.SendStreamingMessage.bind(this);
    this.GetTask = this.GetTask.bind(this);
    this.CancelTask = this.CancelTask.bind(this);
    this.TaskSubscription = this.TaskSubscription.bind(this);
    this.CreateTaskPushNotificationConfig = this.CreateTaskPushNotificationConfig.bind(this);
    this.GetTaskPushNotificationConfig = this.GetTaskPushNotificationConfig.bind(this);
    this.ListTaskPushNotificationConfig = this.ListTaskPushNotificationConfig.bind(this);
    this.GetAgentCard = this.GetAgentCard.bind(this);
    this.DeleteTaskPushNotificationConfig = this.DeleteTaskPushNotificationConfig.bind(this);
  }
  SendMessage(request: SendMessageRequest): Promise<SendMessageResponse> {
    const data = SendMessageRequest.encode(request).finish();
    const promise = this.rpc.request(this.service, "SendMessage", data);
    return promise.then((data) => SendMessageResponse.decode(_m0.Reader.create(data)));
  }

  SendStreamingMessage(request: SendMessageRequest): Observable<StreamResponse> {
    const data = SendMessageRequest.encode(request).finish();
    const result = this.rpc.serverStreamingRequest(this.service, "SendStreamingMessage", data);
    return result.pipe(map((data) => StreamResponse.decode(_m0.Reader.create(data))));
  }

  GetTask(request: GetTaskRequest): Promise<Task> {
    const data = GetTaskRequest.encode(request).finish();
    const promise = this.rpc.request(this.service, "GetTask", data);
    return promise.then((data) => Task.decode(_m0.Reader.create(data)));
  }

  CancelTask(request: CancelTaskRequest): Promise<Task> {
    const data = CancelTaskRequest.encode(request).finish();
    const promise = this.rpc.request(this.service, "CancelTask", data);
    return promise.then((data) => Task.decode(_m0.Reader.create(data)));
  }

  TaskSubscription(request: TaskSubscriptionRequest): Observable<StreamResponse> {
    const data = TaskSubscriptionRequest.encode(request).finish();
    const result = this.rpc.serverStreamingRequest(this.service, "TaskSubscription", data);
    return result.pipe(map((data) => StreamResponse.decode(_m0.Reader.create(data))));
  }

  CreateTaskPushNotificationConfig(
    request: CreateTaskPushNotificationConfigRequest,
  ): Promise<TaskPushNotificationConfig> {
    const data = CreateTaskPushNotificationConfigRequest.encode(request).finish();
    const promise = this.rpc.request(this.service, "CreateTaskPushNotificationConfig", data);
    return promise.then((data) => TaskPushNotificationConfig.decode(_m0.Reader.create(data)));
  }

  GetTaskPushNotificationConfig(request: GetTaskPushNotificationConfigRequest): Promise<TaskPushNotificationConfig> {
    const data = GetTaskPushNotificationConfigRequest.encode(request).finish();
    const promise = this.rpc.request(this.service, "GetTaskPushNotificationConfig", data);
    return promise.then((data) => TaskPushNotificationConfig.decode(_m0.Reader.create(data)));
  }

  ListTaskPushNotificationConfig(
    request: ListTaskPushNotificationConfigRequest,
  ): Promise<ListTaskPushNotificationConfigResponse> {
    const data = ListTaskPushNotificationConfigRequest.encode(request).finish();
    const promise = this.rpc.request(this.service, "ListTaskPushNotificationConfig", data);
    return promise.then((data) => ListTaskPushNotificationConfigResponse.decode(_m0.Reader.create(data)));
  }

  GetAgentCard(request: GetAgentCardRequest): Promise<AgentCard> {
    const data = GetAgentCardRequest.encode(request).finish();
    const promise = this.rpc.request(this.service, "GetAgentCard", data);
    return promise.then((data) => AgentCard.decode(_m0.Reader.create(data)));
  }

  DeleteTaskPushNotificationConfig(request: DeleteTaskPushNotificationConfigRequest): Promise<Empty> {
    const data = DeleteTaskPushNotificationConfigRequest.encode(request).finish();
    const promise = this.rpc.request(this.service, "DeleteTaskPushNotificationConfig", data);
    return promise.then((data) => Empty.decode(_m0.Reader.create(data)));
  }
}

interface Rpc {
  request(service: string, method: string, data: Uint8Array): Promise<Uint8Array>;
  clientStreamingRequest(service: string, method: string, data: Observable<Uint8Array>): Promise<Uint8Array>;
  serverStreamingRequest(service: string, method: string, data: Uint8Array): Observable<Uint8Array>;
  bidirectionalStreamingRequest(service: string, method: string, data: Observable<Uint8Array>): Observable<Uint8Array>;
}

function bytesFromBase64(b64: string): Uint8Array {
  if (globalThis.Buffer) {
    return Uint8Array.from(globalThis.Buffer.from(b64, "base64"));
  } else {
    const bin = globalThis.atob(b64);
    const arr = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; ++i) {
      arr[i] = bin.charCodeAt(i);
    }
    return arr;
  }
}

function base64FromBytes(arr: Uint8Array): string {
  if (globalThis.Buffer) {
    return globalThis.Buffer.from(arr).toString("base64");
  } else {
    const bin: string[] = [];
    arr.forEach((byte) => {
      bin.push(globalThis.String.fromCharCode(byte));
    });
    return globalThis.btoa(bin.join(""));
  }
}

type Builtin = Date | Function | Uint8Array | string | number | boolean | undefined;

export type DeepPartial<T> = T extends Builtin ? T
  : T extends globalThis.Array<infer U> ? globalThis.Array<DeepPartial<U>>
  : T extends ReadonlyArray<infer U> ? ReadonlyArray<DeepPartial<U>>
  : T extends {} ? { [K in keyof T]?: DeepPartial<T[K]> }
  : Partial<T>;

type KeysOfUnion<T> = T extends T ? keyof T : never;
export type Exact<P, I extends P> = P extends Builtin ? P
  : P & { [K in keyof P]: Exact<P[K], I[K]> } & { [K in Exclude<keyof I, KeysOfUnion<P>>]: never };

function toTimestamp(date: Date): Timestamp {
  const seconds = date.getTime() / 1_000;
  const nanos = (date.getTime() % 1_000) * 1_000_000;
  return { seconds, nanos };
}

function fromTimestamp(t: Timestamp): Date {
  let millis = (t.seconds || 0) * 1_000;
  millis += (t.nanos || 0) / 1_000_000;
  return new globalThis.Date(millis);
}

function fromJsonTimestamp(o: any): Date {
  if (o instanceof globalThis.Date) {
    return o;
  } else if (typeof o === "string") {
    return new globalThis.Date(o);
  } else {
    return fromTimestamp(Timestamp.fromJSON(o));
  }
}

function isObject(value: any): boolean {
  return typeof value === "object" && value !== null;
}

function isSet(value: any): boolean {
  return value !== null && value !== undefined;
}
