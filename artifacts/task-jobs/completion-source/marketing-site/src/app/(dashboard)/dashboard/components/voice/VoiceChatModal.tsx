'use client';

import { useCallback, useState, useEffect, useRef } from 'react';
import {
  LiveKitRoom,
  RoomAudioRenderer,
  useConnectionState,
  useRoomContext,
  useTracks,
  useParticipants,
} from '@livekit/components-react';
import { ConnectionState, Track, RoomEvent, DataPacket_Kind } from 'livekit-client';
import '@livekit/components-styles';
import { getVoiceSessionV1VoiceSessionsRoomNameGet, getVoiceSessionStateV1VoiceSessionsRoomNameStateGet } from '@/lib/api';

// Agent state type for polling
type AgentState = 'idle' | 'listening' | 'thinking' | 'speaking' | 'tool_calling' | 'tool_complete' | 'error';

// Data message types from agent
type AgentStateMessage = {
  type: 'agent_state';
  state: AgentState;
  tool_name?: string;
  result?: string;
};

type TranscriptMessage = {
  type: 'transcript';
  role: 'user' | 'agent';
  text: string;
};

type DataMessage = AgentStateMessage | TranscriptMessage;

// Transcript entry for display
type TranscriptEntry = {
  id: string;
  role: 'user' | 'agent' | 'tool';
  text: string;
  toolName?: string;
  toolResult?: string;
  isExpanded?: boolean;
  timestamp: Date;
};

const CloseIcon = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
  </svg>
);

const MicIcon = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
  </svg>
);

const MicOffIcon = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
    <path strokeLinecap="round" strokeLinejoin="round" d="M17 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2" />
  </svg>
);

const VolumeIcon = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
  </svg>
);

const PhoneOffIcon = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M16 8l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2M5 3a2 2 0 00-2 2v1c0 8.284 6.716 15 15 15h1a2 2 0 002-2v-3.28a1 1 0 00-.684-.948l-4.493-1.498a1 1 0 00-1.21.502l-1.13 2.257a11.042 11.042 0 01-5.516-5.517l2.257-1.128a1 1 0 00.502-1.21L9.228 3.683A1 1 0 008.279 3H5z" />
  </svg>
);

const ChevronIcon = ({ className, isExpanded }: { className?: string; isExpanded?: boolean }) => (
  <svg
    className={`${className} transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`}
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
    strokeWidth={2}
  >
    <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
  </svg>
);

const ToolIcon = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
    <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
  </svg>
);

const SpinnerIcon = ({ className }: { className?: string }) => (
  <svg className={`${className} animate-spin`} fill="none" viewBox="0 0 24 24">
    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
  </svg>
);

interface VoiceChatModalProps {
  token: string;
  serverUrl: string;
  roomName: string;
  voice: { id: string; name: string; description: string };
  sessionId?: string;
  userId?: string;
  accessToken?: string;
  apiBaseUrl?: string;
  onClose: () => void;
  children?: React.ReactNode;
}

export default function VoiceChatModal({
  token: initialToken,
  serverUrl: initialServerUrl,
  roomName: initialRoomName,
  voice,
  sessionId,
  userId,
  accessToken,
  apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || 'https://api.codetether.run',
  onClose,
  children,
}: VoiceChatModalProps) {
  const [error, setError] = useState<string | null>(null);
  const [token, setToken] = useState(initialToken);
  const [serverUrl, setServerUrl] = useState(initialServerUrl);
  const [roomName, setRoomName] = useState(initialRoomName);
  const [isConnected, setIsConnected] = useState(false);
  const [agentState, setAgentState] = useState<AgentState>('idle');
  const [currentToolName, setCurrentToolName] = useState<string | null>(null);
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);
  const intentionalDisconnect = useRef(false);

  // Reconnect to an existing session
  const reconnectToSession = useCallback(async (room: string) => {
    if (!userId) return;

    try {
      const { data } = await getVoiceSessionV1VoiceSessionsRoomNameGet({
        path: { room_name: room },
        query: { user_id: userId },
        headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined,
      });

      setToken(((data as unknown as { access_token?: string })?.access_token) || '');
      setServerUrl(((data as unknown as { livekit_url?: string })?.livekit_url) || '');
      setRoomName(((data as unknown as { room_name?: string })?.room_name) || '');
    } catch (err) {
      console.error('Reconnection failed:', err);
    }
  }, [userId, accessToken]);

  const handleError = useCallback((err: Error) => {
    console.error('LiveKit error:', err);
    setError(err.message);
  }, []);

  const handleDisconnected = useCallback(() => {
    console.log('Disconnected from room');
    setIsConnected(false);

    // Auto-reconnect after brief delay if not intentional
    if (roomName && !intentionalDisconnect.current) {
      setTimeout(() => reconnectToSession(roomName), 2000);
    }
  }, [roomName, reconnectToSession]);

  const handleConnected = useCallback(() => {
    console.log('Connected to room');
    setIsConnected(true);
  }, []);

  // Handle data message from agent
  const handleDataMessage = useCallback((message: DataMessage) => {
    if (message.type === 'agent_state') {
      setAgentState(message.state);

      if (message.state === 'tool_calling' && message.tool_name) {
        setCurrentToolName(message.tool_name);
        // Add tool call entry to transcript
        setTranscript(prev => [...prev, {
          id: `tool-${Date.now()}`,
          role: 'tool',
          text: `Calling ${message.tool_name}...`,
          toolName: message.tool_name,
          isExpanded: false,
          timestamp: new Date(),
        }]);
      } else if (message.state === 'tool_complete' && message.tool_name) {
        setCurrentToolName(null);
        // Update the most recent tool entry with the result
        setTranscript(prev => {
          const updated = [...prev];
          for (let i = updated.length - 1; i >= 0; i--) {
            if (updated[i].role === 'tool' && updated[i].toolName === message.tool_name && !updated[i].toolResult) {
              updated[i] = {
                ...updated[i],
                text: `${message.tool_name} completed`,
                toolResult: message.result,
              };
              break;
            }
          }
          return updated;
        });
      } else {
        setCurrentToolName(null);
      }
    } else if (message.type === 'transcript') {
      setTranscript(prev => [...prev, {
        id: `${message.role}-${Date.now()}`,
        role: message.role,
        text: message.text,
        timestamp: new Date(),
      }]);
    }
  }, []);

  // Poll agent state every second when connected (fallback for non-data-channel updates)
  useEffect(() => {
    if (!roomName || !isConnected) return;

    const pollState = async () => {
      try {
        const { data } = await getVoiceSessionStateV1VoiceSessionsRoomNameStateGet({
          path: { room_name: roomName },
          headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined,
        });

        if (data) {
          const state = typeof data === 'string' ? data.replace(/"/g, '') : 'idle';
          if (agentState !== 'tool_calling') {
            setAgentState(state as AgentState);
          }
        }
      } catch {
      }
    };

    pollState();
    const interval = setInterval(pollState, 1000);
    return () => clearInterval(interval);
  }, [roomName, isConnected, accessToken, agentState]);

  // Toggle tool result expansion
  const toggleToolExpansion = useCallback((id: string) => {
    setTranscript(prev => prev.map(entry =>
      entry.id === id ? { ...entry, isExpanded: !entry.isExpanded } : entry
    ));
  }, []);

  // If we have children (like playback controls), just render those
  if (children) {
    return (
      <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
        <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-2xl overflow-hidden">
          <ModalHeader voice={voice} onClose={onClose} />
          <div className="p-6">{children}</div>
          <ModalFooterSimple sessionId={sessionId} roomName={roomName} />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
        <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-2xl overflow-hidden">
          <ModalHeader voice={voice} onClose={onClose} />
          <div className="p-6">
            <div className="text-center py-8">
              <div className="text-red-500 mb-4">Connection Error</div>
              <p className="text-gray-500">{error}</p>
              <button
                onClick={onClose}
                className="mt-4 px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg"
              >
                Close
              </button>
            </div>
          </div>
          <ModalFooterSimple sessionId={sessionId} roomName={roomName} />
        </div>
      </div>
    );
  }

  // Check if mediaDevices is available (requires HTTPS or localhost)
  const mediaDevicesAvailable = typeof navigator !== 'undefined' && !!navigator.mediaDevices;

  // Handle intentional close
  const handleClose = () => {
    intentionalDisconnect.current = true;
    onClose();
  };

  if (!mediaDevicesAvailable) {
    return (
      <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
        <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-2xl overflow-hidden">
          <ModalHeader voice={voice} onClose={onClose} />
          <div className="p-6">
            <div className="text-center py-8">
              <div className="text-red-500 mb-4">Microphone Unavailable</div>
              <p className="text-gray-500">
                Voice chat requires a secure connection (HTTPS). Your browser blocks microphone access on plain HTTP pages.
              </p>
              <p className="text-gray-400 text-sm mt-2">
                Please access this page via HTTPS or localhost to use voice features.
              </p>
              <button
                onClick={onClose}
                className="mt-4 px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg"
              >
                Close
              </button>
            </div>
          </div>
          <ModalFooterSimple sessionId={sessionId} roomName={roomName} />
        </div>
      </div>
    );
  }

  return (
    <LiveKitRoom
      serverUrl={serverUrl}
      token={token}
      connect={true}
      audio={true}
      video={false}
      onError={handleError}
      onDisconnected={handleDisconnected}
      onConnected={handleConnected}
    >
      <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
        <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-2xl overflow-hidden max-h-[90vh] flex flex-col">
          <ModalHeader
            voice={voice}
            onClose={handleClose}
            agentState={agentState}
            currentToolName={currentToolName}
          />
          <div className="flex-1 overflow-hidden flex flex-col">
            <VoiceUI
              voice={voice}
              onClose={handleClose}
              agentState={agentState}
              currentToolName={currentToolName}
              transcript={transcript}
              onToggleToolExpansion={toggleToolExpansion}
              onDataMessage={handleDataMessage}
            />
          </div>
          <ModalFooter
            sessionId={sessionId}
            roomName={roomName}
            agentState={agentState}
            currentToolName={currentToolName}
          />
        </div>
      </div>
      <RoomAudioRenderer />
    </LiveKitRoom>
  );
}

function ModalHeader({
  voice,
  onClose,
  agentState,
  currentToolName
}: {
  voice: { name: string };
  onClose: () => void;
  agentState?: AgentState;
  currentToolName?: string | null;
}) {
  const stateColors: Record<AgentState, string> = {
    idle: 'from-gray-500 to-gray-600',
    listening: 'from-blue-600 to-indigo-600',
    thinking: 'from-yellow-500 to-orange-500',
    speaking: 'from-green-500 to-emerald-600',
    tool_calling: 'from-purple-500 to-violet-600',
    tool_complete: 'from-green-500 to-emerald-600',
    error: 'from-red-500 to-red-600',
  };

  const gradientClass = agentState ? stateColors[agentState] : 'from-blue-600 to-indigo-600';

  const getStateLabel = () => {
    if (agentState === 'tool_calling' && currentToolName) {
      return `Calling ${currentToolName}...`;
    }
    return agentState || 'connecting';
  };

  return (
    <div className={`flex items-center justify-between p-4 bg-linear-to-r ${gradientClass} transition-colors duration-300`}>
      <div className="flex items-center gap-3">
        <div className="p-2 bg-white/20 rounded-lg">
          {agentState === 'tool_calling' ? (
            <SpinnerIcon className="w-5 h-5 text-white" />
          ) : (
            <VolumeIcon className="w-5 h-5 text-white" />
          )}
        </div>
        <div>
          <h2 className="text-white font-semibold">Voice Assistant</h2>
          <p className="text-white/80 text-sm">Voice: {voice.name}</p>
        </div>
      </div>
      <div className="flex items-center gap-3">
        {agentState && (
          <span className="px-2 py-1 bg-white/20 rounded text-white text-xs capitalize flex items-center gap-1">
            {agentState === 'tool_calling' && <SpinnerIcon className="w-3 h-3" />}
            {getStateLabel()}
          </span>
        )}
        <button
          onClick={onClose}
          className="p-2 hover:bg-white/20 rounded-full transition-colors"
        >
          <CloseIcon className="w-5 h-5 text-white" />
        </button>
      </div>
    </div>
  );
}

function ModalFooterSimple({ sessionId, roomName }: { sessionId?: string; roomName: string }) {
  return (
    <div className="px-6 py-4 bg-gray-50 dark:bg-gray-800/50 border-t dark:border-gray-700">
      <div className="flex items-center justify-between text-sm">
        <div className="flex items-center gap-2 text-gray-500">
          <div className="w-2 h-2 rounded-full bg-gray-400" />
          <span>Not connected</span>
        </div>
        <div className="flex items-center gap-4 text-gray-400">
          {sessionId && (
            <span className="font-mono text-xs">Session: {sessionId.slice(0, 8)}...</span>
          )}
          <span>Room: {roomName || 'N/A'}</span>
        </div>
      </div>
    </div>
  );
}

function ModalFooter({
  sessionId,
  roomName,
  agentState,
  currentToolName
}: {
  sessionId?: string;
  roomName: string;
  agentState?: AgentState;
  currentToolName?: string | null;
}) {
  return (
    <div className="px-6 py-4 bg-gray-50 dark:bg-gray-800/50 border-t dark:border-gray-700">
      <div className="flex items-center justify-between text-sm">
        <ConnectionStatus agentState={agentState} currentToolName={currentToolName} />
        <div className="flex items-center gap-4 text-gray-400">
          {sessionId && (
            <span className="font-mono text-xs">Session: {sessionId.slice(0, 8)}...</span>
          )}
          <span>Room: {roomName || 'N/A'}</span>
        </div>
      </div>
    </div>
  );
}

function ConnectionStatus({ agentState, currentToolName }: { agentState?: AgentState; currentToolName?: string | null }) {
  const connectionState = useConnectionState();
  const isConnected = connectionState === ConnectionState.Connected;

  const agentStateColors: Record<AgentState, string> = {
    idle: 'bg-gray-400',
    listening: 'bg-blue-500 animate-pulse',
    thinking: 'bg-yellow-500 animate-pulse',
    speaking: 'bg-green-500 animate-pulse',
    tool_calling: 'bg-purple-500 animate-pulse',
    tool_complete: 'bg-green-500',
    error: 'bg-red-500',
  };

  const dotColor = agentState && isConnected
    ? agentStateColors[agentState]
    : isConnected
      ? 'bg-green-500'
      : 'bg-yellow-500 animate-pulse';

  const getStatusText = () => {
    if (connectionState === ConnectionState.Connecting) return 'Connecting...';
    if (connectionState === ConnectionState.Disconnected) return 'Disconnected';
    if (connectionState === ConnectionState.Reconnecting) return 'Reconnecting...';
    if (connectionState === ConnectionState.Connected) {
      if (agentState === 'tool_calling' && currentToolName) {
        return `Calling ${currentToolName}...`;
      }
      return agentState ? `Agent: ${agentState}` : 'Connected';
    }
    return 'Unknown';
  };

  return (
    <div className="flex items-center gap-2 text-gray-500">
      <div className={`w-2 h-2 rounded-full ${dotColor}`} />
      <span>{getStatusText()}</span>
    </div>
  );
}

// Transcript Panel Component
function TranscriptPanel({
  transcript,
  onToggleToolExpansion
}: {
  transcript: TranscriptEntry[];
  onToggleToolExpansion: (id: string) => void;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new entries
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [transcript]);

  if (transcript.length === 0) {
    return (
      <div className="text-center py-4 text-gray-400 text-sm">
        Conversation transcript will appear here...
      </div>
    );
  }

  return (
    <div
      ref={scrollRef}
      className="h-48 overflow-y-auto space-y-2 pr-2 scrollbar-thin scrollbar-thumb-gray-300 dark:scrollbar-thumb-gray-600"
    >
      {transcript.map((entry) => (
        <TranscriptEntry
          key={entry.id}
          entry={entry}
          onToggle={() => onToggleToolExpansion(entry.id)}
        />
      ))}
    </div>
  );
}

function TranscriptEntry({
  entry,
  onToggle
}: {
  entry: TranscriptEntry;
  onToggle: () => void;
}) {
  const roleStyles = {
    user: 'bg-blue-50 dark:bg-blue-900/30 border-blue-200 dark:border-blue-800',
    agent: 'bg-green-50 dark:bg-green-900/30 border-green-200 dark:border-green-800',
    tool: 'bg-purple-50 dark:bg-purple-900/30 border-purple-200 dark:border-purple-800',
  };

  const roleLabels = {
    user: 'You',
    agent: 'Agent',
    tool: 'Tool',
  };

  const roleLabelColors = {
    user: 'text-blue-600 dark:text-blue-400',
    agent: 'text-green-600 dark:text-green-400',
    tool: 'text-purple-600 dark:text-purple-400',
  };

  const isToolEntry = entry.role === 'tool';
  const hasResult = isToolEntry && entry.toolResult;
  const isLoading = isToolEntry && !entry.toolResult;

  return (
    <div className={`p-3 rounded-lg border ${roleStyles[entry.role]} transition-all`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0 flex-1">
          {isToolEntry && (
            isLoading ? (
              <SpinnerIcon className="w-4 h-4 text-purple-500 shrink-0" />
            ) : (
              <ToolIcon className="w-4 h-4 text-purple-500 shrink-0" />
            )
          )}
          <span className={`text-xs font-semibold ${roleLabelColors[entry.role]}`}>
            {roleLabels[entry.role]}
          </span>
          <span className="text-xs text-gray-400">
            {entry.timestamp.toLocaleTimeString()}
          </span>
        </div>
        {hasResult && (
          <button
            onClick={onToggle}
            className="p-1 hover:bg-white/50 dark:hover:bg-black/20 rounded transition-colors shrink-0"
          >
            <ChevronIcon className="w-4 h-4 text-gray-500" isExpanded={entry.isExpanded} />
          </button>
        )}
      </div>
      <p className="text-sm text-gray-700 dark:text-gray-300 mt-1 wrap-break-word">
        {entry.text}
      </p>
      {hasResult && entry.isExpanded && (
        <div className="mt-2 p-2 bg-white/50 dark:bg-black/20 rounded text-xs font-mono text-gray-600 dark:text-gray-400 whitespace-pre-wrap wrap-break-word max-h-32 overflow-y-auto">
          {entry.toolResult}
        </div>
      )}
    </div>
  );
}

function VoiceUI({
  voice,
  onClose,
  agentState,
  currentToolName,
  transcript,
  onToggleToolExpansion,
  onDataMessage,
}: {
  voice: { name: string; description: string };
  onClose: () => void;
  agentState?: AgentState;
  currentToolName?: string | null;
  transcript: TranscriptEntry[];
  onToggleToolExpansion: (id: string) => void;
  onDataMessage: (message: DataMessage) => void;
}) {
  const room = useRoomContext();
  const connectionState = useConnectionState();
  const participants = useParticipants();
  const [isMuted, setIsMuted] = useState(false);

  // Track audio sources (used for visualization reference)
  useTracks([Track.Source.Microphone, Track.Source.ScreenShareAudio]);

  const isConnected = connectionState === ConnectionState.Connected;
  const agentParticipant = participants.find(p => p.identity.startsWith('agent'));
  const hasAgent = !!agentParticipant;

  // Listen for data messages from the agent
  useEffect(() => {
    if (!room) return;

    const handleDataReceived = (payload: Uint8Array) => {
      try {
        const decoder = new TextDecoder();
        const jsonStr = decoder.decode(payload);
        const message = JSON.parse(jsonStr) as DataMessage;

        if (message.type === 'agent_state' || message.type === 'transcript') {
          onDataMessage(message);
        }
      } catch (err) {
        console.error('Failed to parse data message:', err);
      }
    };

    room.on(RoomEvent.DataReceived, handleDataReceived);

    return () => {
      room.off(RoomEvent.DataReceived, handleDataReceived);
    };
  }, [room, onDataMessage]);

  // Agent state styling
  const agentStateConfig: Record<AgentState, { gradient: string; label: string; animate: boolean }> = {
    idle: { gradient: 'from-gray-400 to-gray-600', label: 'Idle', animate: false },
    listening: { gradient: 'from-blue-400 to-blue-600', label: 'Listening...', animate: true },
    thinking: { gradient: 'from-yellow-400 to-orange-500', label: 'Thinking...', animate: true },
    speaking: { gradient: 'from-green-400 to-green-600', label: 'Speaking...', animate: true },
    tool_calling: { gradient: 'from-purple-400 to-violet-600', label: `Calling ${currentToolName || 'tool'}...`, animate: true },
    tool_complete: { gradient: 'from-green-400 to-green-600', label: 'Tool completed', animate: false },
    error: { gradient: 'from-red-400 to-red-600', label: 'Error', animate: false },
  };

  const currentStateConfig = agentState ? agentStateConfig[agentState] : null;

  const toggleMute = useCallback(async () => {
    const localParticipant = room.localParticipant;
    if (localParticipant) {
      await localParticipant.setMicrophoneEnabled(isMuted);
      setIsMuted(!isMuted);
    }
  }, [room, isMuted]);

  const handleEndCall = useCallback(() => {
    room.disconnect();
    onClose();
  }, [room, onClose]);

  // Determine avatar gradient based on agent state (if available) or connection status
  const getAvatarGradient = () => {
    if (currentStateConfig) return `bg-gradient-to-br ${currentStateConfig.gradient}`;
    if (hasAgent) return 'bg-gradient-to-br from-green-400 to-green-600';
    if (isConnected) return 'bg-gradient-to-br from-blue-400 to-blue-600';
    return 'bg-gradient-to-br from-gray-400 to-gray-600';
  };

  const shouldAnimate = currentStateConfig?.animate || (!hasAgent && isConnected);

  return (
    <div className="flex flex-col p-6 overflow-hidden">
      {/* Agent avatar with state indicator */}
      <div className="flex flex-col items-center">
        <div className="relative mb-4">
          <div
            className={`w-24 h-24 rounded-full flex items-center justify-center transition-all duration-300 ${getAvatarGradient()} ${shouldAnimate ? 'animate-pulse' : ''}`}
          >
            {agentState === 'tool_calling' ? (
              <SpinnerIcon className="w-12 h-12 text-white" />
            ) : (
              <VolumeIcon className="w-12 h-12 text-white" />
            )}
          </div>

          <div className="absolute -bottom-2 left-1/2 -translate-x-1/2 bg-white dark:bg-gray-800 px-3 py-1 rounded-full shadow-md">
            <span className={`text-xs font-medium px-2 py-1 rounded-full flex items-center gap-1 ${agentState === 'speaking' ? 'text-green-600 bg-green-100' :
                agentState === 'listening' ? 'text-blue-600 bg-blue-100' :
                  agentState === 'thinking' ? 'text-yellow-600 bg-yellow-100' :
                    agentState === 'tool_calling' ? 'text-purple-600 bg-purple-100' :
                      agentState === 'error' ? 'text-red-600 bg-red-100' :
                        hasAgent ? 'text-green-600 bg-green-100' :
                          isConnected ? 'text-blue-600 bg-blue-100' :
                            'text-gray-600 bg-gray-100'
              }`}>
              {agentState === 'tool_calling' && <SpinnerIcon className="w-3 h-3" />}
              {currentStateConfig?.label || (hasAgent ? 'Agent Connected' : isConnected ? 'Waiting for Agent...' : 'Connecting...')}
            </span>
          </div>
        </div>

        {/* Audio visualization */}
        <div className="w-full max-w-xs mb-4">
          <div className="flex items-end justify-center gap-1 h-12">
            {[...Array(20)].map((_, i) => {
              const isActive = agentState === 'speaking' || agentState === 'listening' || hasAgent;
              const baseHeight = isActive ? 20 + Math.sin(Date.now() / 200 + i) * 15 : 4;

              const barGradient = agentState === 'speaking'
                ? 'bg-gradient-to-t from-green-500 to-emerald-400'
                : agentState === 'listening'
                  ? 'bg-gradient-to-t from-blue-500 to-blue-400'
                  : agentState === 'thinking'
                    ? 'bg-gradient-to-t from-yellow-500 to-orange-400'
                    : agentState === 'tool_calling'
                      ? 'bg-gradient-to-t from-purple-500 to-violet-400'
                      : hasAgent
                        ? 'bg-gradient-to-t from-green-500 to-emerald-400'
                        : 'bg-gradient-to-t from-blue-500 to-indigo-500';

              return (
                <div
                  key={i}
                  className={`w-2 rounded-t transition-all duration-75 ${barGradient}`}
                  style={{ height: `${baseHeight}%` }}
                />
              );
            })}
          </div>
        </div>

        {/* Voice info */}
        <div className="text-center mb-4">
          <p className="text-base font-medium">{voice.name}</p>
          <p className="text-xs text-gray-500 dark:text-gray-400">{voice.description}</p>
        </div>

        {/* Controls */}
        <div className="flex items-center gap-4 mb-4">
          <button
            onClick={toggleMute}
            disabled={!isConnected}
            className={`p-3 rounded-full transition-all ${isMuted
                ? 'bg-red-100 text-red-600 hover:bg-red-200'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              } disabled:opacity-50`}
          >
            {isMuted ? <MicOffIcon className="w-5 h-5" /> : <MicIcon className="w-5 h-5" />}
          </button>

          <button
            onClick={handleEndCall}
            className="p-3 bg-red-600 text-white rounded-full hover:bg-red-700 transition-all shadow-lg hover:shadow-xl"
          >
            <PhoneOffIcon className="w-5 h-5" />
          </button>
        </div>

        {/* Participant count */}
        <div className="text-xs text-gray-400 mb-4">
          {participants.length} participant{participants.length !== 1 ? 's' : ''} in room
        </div>
      </div>

      {/* Transcript Panel */}
      <div className="border-t dark:border-gray-700 pt-4">
        <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2 flex items-center gap-2">
          Transcript
          {agentState === 'tool_calling' && (
            <span className="text-xs font-normal text-purple-600 dark:text-purple-400 flex items-center gap-1">
              <SpinnerIcon className="w-3 h-3" />
              Tool executing...
            </span>
          )}
        </h3>
        <TranscriptPanel
          transcript={transcript}
          onToggleToolExpansion={onToggleToolExpansion}
        />
      </div>
    </div>
  );
}
