'use client';

import { useState } from 'react';
import { useSession } from 'next-auth/react';
import { listVoicesV1VoiceVoicesGet, createVoiceSessionV1VoiceSessionsPost } from '@/lib/api';

const generateUuid = () => {
  if (typeof crypto !== 'undefined') {
    if (typeof crypto.randomUUID === 'function') {
      return crypto.randomUUID();
    }
    if (typeof crypto.getRandomValues === 'function') {
      const bytes = new Uint8Array(16);
      crypto.getRandomValues(bytes);
      bytes[6] = (bytes[6] & 0x0f) | 0x40;
      bytes[8] = (bytes[8] & 0x3f) | 0x80;
      const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0'));
      return `${hex.slice(0, 4).join('')}-${hex.slice(4, 6).join('')}-${hex.slice(6, 8).join('')}-${hex.slice(8, 10).join('')}-${hex.slice(10, 16).join('')}`;
    }
  }
  return `voice-${Date.now()}-${Math.random().toString(16).slice(2)}`;
};

// SVG Icon
const MicIcon = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
  </svg>
);

interface VoiceChatButtonProps {
  codebaseId?: string;
  sessionId?: string;
  mode: 'chat' | 'playback';
  playbackStyle?: 'verbatim' | 'summary';
}

interface VoiceSession {
  room_name: string;
  access_token: string;
  livekit_url: string;
  voice: string;
  mode: string;
  expires_at: string;
}

interface Voice {
  id: string;
  name: string;
  description: string;
}

export default function VoiceChatButton({
  codebaseId,
  sessionId,
  mode,
  playbackStyle = 'verbatim',
}: VoiceChatButtonProps) {
  const { data: session } = useSession();
  const [isOpen, setIsOpen] = useState(false);
  const [selectedVoice, setSelectedVoice] = useState<Voice | null>(null);
  const [connectionInfo, setConnectionInfo] = useState<VoiceSession | null>(null);
  const [showVoiceSelector, setShowVoiceSelector] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  // Generate a persistent user ID for session reconnection
  const [userId] = useState(() => {
    if (typeof window === 'undefined') {
      return generateUuid();
    }
    const stored = localStorage.getItem('voice_user_id');
    if (stored) {
      return stored;
    }
    const id = generateUuid();
    localStorage.setItem('voice_user_id', id);
    return id;
  });

  const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || 'https://api.codetether.run';

  const fetchVoices = async () => {
    try {
      const { data } = await listVoicesV1VoiceVoicesGet({
        headers: session?.accessToken ? { Authorization: `Bearer ${session.accessToken}` } : undefined,
      });
      return ((data as unknown as { voices?: Voice[] })?.voices) || [];
    } catch {
      return [];
    }
  };

  const startSession = async (voice: Voice) => {
    setIsLoading(true);
    try {
      const { data } = await createVoiceSessionV1VoiceSessionsPost({
        body: {
          voice: voice.id,
          codebase_id: codebaseId,
          session_id: sessionId,
          mode: mode,
          playback_style: playbackStyle,
          user_id: userId,
        },
        headers: session?.accessToken ? { Authorization: `Bearer ${session.accessToken}` } : undefined,
      });
      setConnectionInfo(data as VoiceSession);
      setIsOpen(true);
    } catch (e) {
      console.error('Failed to start voice session:', e);
    } finally {
      setIsLoading(false);
    }
  };

  const handleVoiceSelect = async (voice: Voice) => {
    setSelectedVoice(voice);
    setShowVoiceSelector(false);
    // Start session immediately after voice selection
    await startSession(voice);
  };

  const handleClick = async () => {
    if (mode === 'chat') {
      if (!selectedVoice) {
        setShowVoiceSelector(true);
      } else {
        await startSession(selectedVoice);
      }
    } else if (mode === 'playback' && sessionId) {
      setIsOpen(true);
    }
  };

  return (
    <>
      <button
        onClick={handleClick}
        disabled={isLoading}
        className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
      >
        <MicIcon className="w-4 h-4" />
        {isLoading ? 'Connecting...' : mode === 'chat' ? 'Voice Chat' : 'Playback Session'}
      </button>

      {showVoiceSelector && (
        <VoiceSelector
          selected={selectedVoice}
          onSelect={handleVoiceSelect}
          onClose={() => setShowVoiceSelector(false)}
        />
      )}

      {isOpen && connectionInfo && mode === 'chat' && selectedVoice && (
        <VoiceChatModal
          token={connectionInfo.access_token}
          serverUrl={connectionInfo.livekit_url}
          roomName={connectionInfo.room_name}
          voice={selectedVoice}
          sessionId={sessionId}
          userId={userId}
          accessToken={session?.accessToken}
          apiBaseUrl={apiBaseUrl}
          onClose={() => {
            setIsOpen(false);
            setConnectionInfo(null);
          }}
        />
      )}

      {isOpen && mode === 'playback' && sessionId && (
        <VoiceChatModal
          token=""
          serverUrl=""
          roomName=""
          voice={{ id: 'playback', name: 'Playback', description: '' }}
          sessionId={sessionId}
          onClose={() => setIsOpen(false)}
        >
          <PlaybackControls
            sessionId={sessionId}
            onPlayback={(mode) => console.log('Playback mode:', mode)}
          />
        </VoiceChatModal>
      )}
    </>
  );
}

import VoiceSelector from './VoiceSelector';
import VoiceChatModal from './VoiceChatModal';
import PlaybackControls from './PlaybackControls';
