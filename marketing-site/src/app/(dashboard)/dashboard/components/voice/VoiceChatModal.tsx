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
import { ConnectionState, Track } from 'livekit-client';
import '@livekit/components-styles';

// Agent state type for polling
type AgentState = 'idle' | 'listening' | 'thinking' | 'speaking' | 'error';

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
  const intentionalDisconnect = useRef(false);

  // Reconnect to an existing session
  const reconnectToSession = useCallback(async (room: string) => {
    if (!userId) return;
    
    try {
      const headers: HeadersInit = accessToken 
        ? { 'Authorization': `Bearer ${accessToken}` } 
        : {};
      
      const res = await fetch(
        `${apiBaseUrl}/v1/voice/sessions/${room}?user_id=${userId}`,
        { headers }
      );
      
      if (res.ok) {
        const data = await res.json();
        setToken(data.access_token);
        setServerUrl(data.livekit_url);
        setRoomName(data.room_name);
      }
    } catch (err) {
      console.error('Reconnection failed:', err);
    }
  }, [apiBaseUrl, userId, accessToken]);

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

  // Poll agent state every second when connected
  useEffect(() => {
    if (!roomName || !isConnected) return;

    const pollState = async () => {
      try {
        const headers: HeadersInit = accessToken 
          ? { 'Authorization': `Bearer ${accessToken}` } 
          : {};
        
        const res = await fetch(
          `${apiBaseUrl}/v1/voice/sessions/${roomName}/state`,
          { headers }
        );
        
        if (res.ok) {
          const state = await res.text();
          setAgentState(state.replace(/"/g, '') as AgentState);
        }
      } catch {
        // Ignore polling errors
      }
    };

    pollState(); // Initial poll
    const interval = setInterval(pollState, 1000);
    return () => clearInterval(interval);
  }, [roomName, isConnected, apiBaseUrl, accessToken]);

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

  // Handle intentional close
  const handleClose = useCallback(() => {
    intentionalDisconnect.current = true;
    onClose();
  }, [onClose]);

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
        <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-2xl overflow-hidden">
          <ModalHeader voice={voice} onClose={handleClose} agentState={agentState} />
          <div className="p-6">
            <VoiceUI voice={voice} onClose={handleClose} agentState={agentState} />
          </div>
          <ModalFooter sessionId={sessionId} roomName={roomName} agentState={agentState} />
        </div>
      </div>
      <RoomAudioRenderer />
    </LiveKitRoom>
  );
}

function ModalHeader({ voice, onClose, agentState }: { voice: { name: string }; onClose: () => void; agentState?: AgentState }) {
  const stateColors: Record<AgentState, string> = {
    idle: 'from-gray-500 to-gray-600',
    listening: 'from-blue-600 to-indigo-600',
    thinking: 'from-yellow-500 to-orange-500',
    speaking: 'from-green-500 to-emerald-600',
    error: 'from-red-500 to-red-600',
  };

  const gradientClass = agentState ? stateColors[agentState] : 'from-blue-600 to-indigo-600';

  return (
    <div className={`flex items-center justify-between p-4 bg-gradient-to-r ${gradientClass} transition-colors duration-300`}>
      <div className="flex items-center gap-3">
        <div className="p-2 bg-white/20 rounded-lg">
          <VolumeIcon className="w-5 h-5 text-white" />
        </div>
        <div>
          <h2 className="text-white font-semibold">Voice Assistant</h2>
          <p className="text-white/80 text-sm">Voice: {voice.name}</p>
        </div>
      </div>
      {agentState && (
        <span className="px-2 py-1 bg-white/20 rounded text-white text-xs capitalize">
          {agentState}
        </span>
      )}
      <button
        onClick={onClose}
        className="p-2 hover:bg-white/20 rounded-full transition-colors"
      >
        <CloseIcon className="w-5 h-5 text-white" />
      </button>
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

function ModalFooter({ sessionId, roomName, agentState }: { sessionId?: string; roomName: string; agentState?: AgentState }) {
  return (
    <div className="px-6 py-4 bg-gray-50 dark:bg-gray-800/50 border-t dark:border-gray-700">
      <div className="flex items-center justify-between text-sm">
        <ConnectionStatus agentState={agentState} />
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

function ConnectionStatus({ agentState }: { agentState?: AgentState }) {
  const connectionState = useConnectionState();
  const isConnected = connectionState === ConnectionState.Connected;

  const agentStateColors: Record<AgentState, string> = {
    idle: 'bg-gray-400',
    listening: 'bg-blue-500 animate-pulse',
    thinking: 'bg-yellow-500 animate-pulse',
    speaking: 'bg-green-500 animate-pulse',
    error: 'bg-red-500',
  };

  const dotColor = agentState && isConnected 
    ? agentStateColors[agentState] 
    : isConnected 
      ? 'bg-green-500' 
      : 'bg-yellow-500 animate-pulse';

  return (
    <div className="flex items-center gap-2 text-gray-500">
      <div className={`w-2 h-2 rounded-full ${dotColor}`} />
      <span>
        {connectionState === ConnectionState.Connecting && 'Connecting...'}
        {connectionState === ConnectionState.Connected && (agentState ? `Agent: ${agentState}` : 'Connected')}
        {connectionState === ConnectionState.Disconnected && 'Disconnected'}
        {connectionState === ConnectionState.Reconnecting && 'Reconnecting...'}
      </span>
    </div>
  );
}

function VoiceUI({ voice, onClose, agentState }: { voice: { name: string; description: string }; onClose: () => void; agentState?: AgentState }) {
  const room = useRoomContext();
  const connectionState = useConnectionState();
  const participants = useParticipants();
  const [isMuted, setIsMuted] = useState(false);

  // Get audio tracks to visualize
  const audioTracks = useTracks([Track.Source.Microphone, Track.Source.ScreenShareAudio]);

  const isConnected = connectionState === ConnectionState.Connected;
  const agentParticipant = participants.find(p => p.identity.startsWith('agent'));
  const hasAgent = !!agentParticipant;

  // Agent state styling
  const agentStateConfig: Record<AgentState, { gradient: string; label: string; animate: boolean }> = {
    idle: { gradient: 'from-gray-400 to-gray-600', label: 'Idle', animate: false },
    listening: { gradient: 'from-blue-400 to-blue-600', label: 'Listening...', animate: true },
    thinking: { gradient: 'from-yellow-400 to-orange-500', label: 'Thinking...', animate: true },
    speaking: { gradient: 'from-green-400 to-green-600', label: 'Speaking...', animate: true },
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
    <div className="flex flex-col items-center py-8">
      {/* Agent avatar with state indicator */}
      <div className="relative mb-8">
        <div
          className={`w-32 h-32 rounded-full flex items-center justify-center transition-all duration-300 ${getAvatarGradient()} ${shouldAnimate ? 'animate-pulse' : ''}`}
        >
          <VolumeIcon className="w-16 h-16 text-white" />
        </div>

        <div className="absolute -bottom-2 left-1/2 -translate-x-1/2 bg-white dark:bg-gray-800 px-3 py-1 rounded-full shadow-md">
          <span className={`text-xs font-medium px-2 py-1 rounded-full ${
            agentState === 'speaking' ? 'text-green-600 bg-green-100' :
            agentState === 'listening' ? 'text-blue-600 bg-blue-100' :
            agentState === 'thinking' ? 'text-yellow-600 bg-yellow-100' :
            agentState === 'error' ? 'text-red-600 bg-red-100' :
            hasAgent ? 'text-green-600 bg-green-100' : 
            isConnected ? 'text-blue-600 bg-blue-100' : 
            'text-gray-600 bg-gray-100'
          }`}>
            {currentStateConfig?.label || (hasAgent ? 'Agent Connected' : isConnected ? 'Waiting for Agent...' : 'Connecting...')}
          </span>
        </div>
      </div>

      {/* Audio visualization */}
      <div className="w-full max-w-xs mb-8">
        <div className="flex items-end justify-center gap-1 h-16">
          {[...Array(20)].map((_, i) => {
            const isActive = agentState === 'speaking' || agentState === 'listening' || hasAgent;
            const baseHeight = isActive ? 20 + Math.sin(Date.now() / 200 + i) * 15 : 4;
            
            const barGradient = agentState === 'speaking' 
              ? 'bg-gradient-to-t from-green-500 to-emerald-400'
              : agentState === 'listening'
              ? 'bg-gradient-to-t from-blue-500 to-blue-400'
              : agentState === 'thinking'
              ? 'bg-gradient-to-t from-yellow-500 to-orange-400'
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
      <div className="text-center mb-8">
        <p className="text-lg font-medium">{voice.name}</p>
        <p className="text-sm text-gray-500 dark:text-gray-400">{voice.description}</p>
        {agentState === 'listening' && (
          <p className="text-xs text-blue-600 mt-2">Voice agent is listening</p>
        )}
        {agentState === 'speaking' && (
          <p className="text-xs text-green-600 mt-2">Voice agent is speaking</p>
        )}
        {agentState === 'thinking' && (
          <p className="text-xs text-yellow-600 mt-2">Voice agent is thinking...</p>
        )}
        {!agentState && hasAgent && (
          <p className="text-xs text-green-600 mt-2">Voice agent is connected</p>
        )}
      </div>

      {/* Controls */}
      <div className="flex items-center gap-4">
        <button
          onClick={toggleMute}
          disabled={!isConnected}
          className={`p-4 rounded-full transition-all ${
            isMuted
              ? 'bg-red-100 text-red-600 hover:bg-red-200'
              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
          } disabled:opacity-50`}
        >
          {isMuted ? <MicOffIcon className="w-6 h-6" /> : <MicIcon className="w-6 h-6" />}
        </button>

        <button
          onClick={handleEndCall}
          className="p-4 bg-red-600 text-white rounded-full hover:bg-red-700 transition-all shadow-lg hover:shadow-xl"
        >
          <PhoneOffIcon className="w-6 h-6" />
        </button>
      </div>

      {/* Participant count */}
      <div className="mt-6 text-xs text-gray-400">
        {participants.length} participant{participants.length !== 1 ? 's' : ''} in room
      </div>
    </div>
  );
}
