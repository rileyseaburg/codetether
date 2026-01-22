export type Resolver<T, P = {}, C = any> = (
  parent: T,
  args: P,
  context: C,
  info: any
) => Promise<unknown> | unknown;

export interface OpenCodeGraphQLResolvers {
  Query: {
    project: Resolver<unknown, { id: string }>;
    projects: Resolver<unknown>;
    session: Resolver<unknown, { id: string }>;
    sessions: Resolver<unknown, { projectId?: string }>;
    message: Resolver<unknown, { sessionId: string; messageId: string }>;
    messages: Resolver<unknown, { sessionId: string }>;
    todo: Resolver<unknown, { sessionId: string }>;
    sessionStats: Resolver<unknown, { sessionId: string }>;
  };
  Mutation: {
    createProject: Resolver<unknown, { project: any }>;
    createSession: Resolver<unknown, { session: any }>;
    updateSession: Resolver<unknown, { id: string; updates: any }>;
    createMessage: Resolver<unknown, { sessionId: string; message: any }>;
    createTodo: Resolver<unknown, { sessionId: string; todoList: any[] }>;
    updateTodo: Resolver<unknown, { sessionId: string; todoList: any[] }>;
  };
  Project: {
    sessions: Resolver<any>;
    id: string;
    worktree: string;
    vcs: string | null;
    time: any;
    sandboxes: any[];
  };
  Session: {
    project: Resolver<any>;
    messages: Resolver<any>;
    diff: Resolver<any>;
    todo: Resolver<any>;
    stats: Resolver<any>;
    id: string;
    version: string;
    projectID: string;
    directory: string;
    title: string;
    time: any;
    summary: any;
  };
  Message: {
    session: Resolver<any>;
    parts: Resolver<any>;
    parent: Resolver<any>;
    children: Resolver<any>;
    id: string;
    sessionID: string;
    role: string;
    time: any;
    summary: any;
    parentID: string | null;
    modelID: string | null;
    providerID: string | null;
    mode: string | null;
    path: any;
    cost: number | null;
    tokens: any;
    agent: string | null;
    model: any;
  };
  Part: {
    message: Resolver<any>;
    id: string;
    sessionID: string;
    messageID: string;
    type: string;
    text: string;
    time: any;
  };
  Diff: {
    file: string;
    before: string;
    after: string;
    additions: number;
    deletions: number;
  };
  Todo: {
    id: string;
    content: string;
    status: string;
    priority: string;
  };
  TimeRange: {
    created: number;
    updated: number;
  };
  MessageTime: {
    created: number;
    completed: number | null;
  };
  PartTime: {
    start: number | null;
    end: number | null;
  };
  SessionSummary: {
    additions: number | null;
    deletions: number | null;
    files: number | null;
  };
  MessageSummary: {
    title: string | null;
    diffs: Diff[];
  };
  MessagePath: {
    cwd: string | null;
    root: string | null;
  };
  TokenCache: {
    read: number | null;
    write: number | null;
  };
  MessageTokens: {
    input: number | null;
    output: number | null;
    reasoning: number | null;
    cache: TokenCache | null;
  };
  MessageModel: {
    providerID: string | null;
    modelID: string | null;
  };
}

export const OpenCodeGraphQLSchema = /* GraphQL */ `
  """
  Core types for OpenCode storage data
  """
  
  scalar JSON
  
  type TimeRange {
    created: Float!
    updated: Float!
  }

  type MessageTime {
    created: Float!
    completed: Float
  }

  type PartTime {
    start: Float
    end: Float
  }

  type TokenCache {
    read: Float
    write: Float
  }

  type MessageTokens {
    input: Float
    output: Float
    reasoning: Float
    cache: TokenCache
  }

  type MessageModel {
    providerID: String
    modelID: String
  }

  type MessagePath {
    cwd: String
    root: String
  }

  type Diff {
    file: String!
    before: String!
    after: String!
    additions: Int!
    deletions: Int!
  }

  type MessageSummary {
    title: String
    diffs: [Diff!]
  }

  type SessionSummary {
    additions: Int
    deletions: Int
    files: Int
  }

  """
  A Project represents a codebase/environment being worked on
  """
  type Project {
    """
    Unique project identifier (UUID format)
    """
    id: ID!
    
    """
    Working directory path
    """
    worktree: String!
    
    """
    Version control system (e.g., git)
    """
    vcs: String
    
    """
    Timestamp information
    """
    time: TimeRange!
    
    """
    List of sandbox configurations
    """
    sandboxes: [JSON!]!
    
    """
    All sessions belonging to this project
    """
    sessions: [Session!]!
  }

  """
  A Session represents a complete coding conversation/session
  """
  type Session {
    """
    Unique session identifier with ses_ prefix
    """
    id: ID!
    
    """
    Software version string
    """
    version: String!
    
    """
    Reference to associated project
    """
    projectID: String!
    
    """
    Working directory path
    """
    directory: String!
    
    """
    Session title/description
    """
    title: String!
    
    """
    Timestamp information
    """
    time: TimeRange!
    
    """
    Session summary statistics
    """
    summary: SessionSummary
    
    """
    The associated project
    """
    project: Project
    
    """
    All messages in this session
    """
    messages: [Message!]!
    
    """
    File changes made during this session
    """
    diff: [Diff!]
    
    """
    Todo items for this session
    """
    todo: [Todo!]!
    
    """
    Computed statistics for this session
    """
    stats: SessionStats
  }

  """
  A Message represents a single chat message in a session
  """
  type Message {
    """
    Unique message identifier with msg_ prefix
    """
    id: ID!
    
    """
    Reference to parent session
    """
    sessionID: String!
    
    """
    Message role: user or assistant
    """
    role: String! 
    
    """
    Timestamp information
    """
    time: MessageTime!
    
    """
    Optional message summary
    """
    summary: MessageSummary
    
    """
    Parent message ID for threading
    """
    parentID: String
    
    """
    Model identifier used (for assistant messages)
    """
    modelID: String
    
    """
    Provider ID
    """
    providerID: String
    
    """
    Session mode
    """
    mode: String
    
    """
    Path information at time of message
    """
    path: MessagePath
    
    """
    Cost of request
    """
    cost: Float
    
    """
    Token usage information
    """
    tokens: MessageTokens
    
    """
    Agent identifier
    """
    agent: String
    
    """
    Alternative model information
    """
    model: MessageModel
    
    """
    The associated session
    """
    session: Session
    
    """
    All parts (content blocks) in this message
    """
    parts: [Part!]!
    
    """
    Parent message in thread
    """
    parent: Message
    
    """
    Child messages in thread
    """
    children: [Message!]!
  }

  """
  A Part represents a content block within a message
  """
  type Part {
    """
    Unique part identifier with prt_ prefix
    """
    id: ID!
    
    """
    Parent session ID
    """
    sessionID: String!
    
    """
    Parent message ID
    """
    messageID: String!
    
    """
    Part type: text or other types
    """
    type: String!
    
    """
    Text content
    """
    text: String!
    
    """
    Timestamp information
    """
    time: PartTime
    
    """
    The associated message
    """
    message: Message
  }

  """
  A Todo represents a task item
  """
  type Todo {
    """
    Todo item identifier
    """
    id: ID!
    
    """
    Todo description
    """
    content: String!
    
    """
    Todo status
    """
    status: String!
    
    """
    Todo priority
    """
    priority: String!
  }

  """
  Computed statistics for a session
  """
  type SessionStats {
    """
    Total number of messages
    """
    messageCount: Int!
    
    """
    Number of user messages
    """
    userMessageCount: Int!
    
    """
    Number of assistant messages
    """
    assistantMessageCount: Int!
    
    """
    Total processing time in milliseconds
    """
    totalTime: Float!
    
    """
    Total cost of all messages
    """
    totalCost: Float!
    
    """
    Total tokens used
    """
    totalTokens: Int!
  }

  """
  Todo statistics
  """
  type TodoStats {
    """
    Total todo count
    """
    total: Int!
    
    """
    Completed todos
    """
    completed: Int!
    
    """
    Pending todos
    """
    pending: Int!
    
    """
    In-progress todos
    """
    inProgress: Int!
    
    """
    Cancelled todos
    """
    cancelled: Int!
  }

  """
  Query operations
  """
  type Query {
    """
    Get a project by ID
    """
    project(id: ID!): Project
    
    """
    List all projects
    """
    projects: [Project!]!
    
    """
    Get a session by ID
    """
    session(id: ID!): Session
    
    """
    List sessions, optionally filtered by project
    """
    sessions(projectId: ID): [Session!]!
    
    """
    Get a specific message
    """
    message(sessionId: ID!, messageId: ID!): Message
    
    """
    Get all messages in a session
    """
    messages(sessionId: ID!): [Message!]!
    
    """
    Get todos for a session
    """
    todo(sessionId: ID!): [Todo!]!
    
    """
    Get statistics for a session
    """
    sessionStats(sessionId: ID!): SessionStats!
    
    """
    Get todo statistics for a session
    """
    todoStats(sessionId: ID!): TodoStats!
  }

  """
  Input types for mutations
  """
  input ProjectInput {
    id: ID!
    worktree: String!
    vcs: String
  }

  input SessionInput {
    id: ID!
    version: String!
    projectID: String!
    directory: String!
    title: String!
  }

  input MessageInput {
    id: ID!
    sessionID: String!
    role: String!
    time: MessageTimeInput!
    parentID: String
    modelID: String
    providerID: String
    mode: String
    path: MessagePathInput
    cost: Float
    tokens: MessageTokensInput
    agent: String
  }

  input MessageTimeInput {
    created: Float!
    completed: Float
  }

  input MessagePathInput {
    cwd: String
    root: String
  }

  input MessageTokensInput {
    input: Float
    output: Float
    reasoning: Float
    cache: TokenCacheInput
  }

  input TokenCacheInput {
    read: Float
    write: Float
  }

  input TodoInput {
    id: ID!
    content: String!
    status: String!
    priority: String!
  }

  """
  Mutation operations
  """
  type Mutation {
    """
    Create a new project
    """
    createProject(project: ProjectInput!): Project!
    
    """
    Create a new session
    """
    createSession(session: SessionInput!): Session!
    
    """
    Update an existing session
    """
    updateSession(id: ID!, updates: JSON!): Session!
    
    """
    Create a new message
    """
    createMessage(sessionId: ID!, message: MessageInput!): Message!
    
    """
    Create or update todos for a session
    """
    updateTodo(sessionId: ID!, todoList: [TodoInput!]!): [Todo!]!
    
    """
    Delete a session
    """
    deleteSession(id: ID!): Boolean!
  }
`;