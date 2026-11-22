'use client';

import { useState } from 'react';
import { useTenantApi } from '@/hooks/useTenantApi';

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
  compact?: boolean;
}

interface VoiceSession {
  room_name: string;
  access_token: string;
  livekit_url: string;
  voice: string;
  mode: string;
  expires_at: string;
  user_id: string;
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
  compact = false,
}: VoiceChatButtonProps) {
  const { tenantFetch } = useTenantApi();
  const [error, setError] = useState<string | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [selectedVoice, setSelectedVoice] = useState<Voice | null>(null);
  const [connectionInfo, setConnectionInfo] = useState<VoiceSession | null>(null);
  const [showVoiceSelector, setShowVoiceSelector] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const startSession = async (voice: Voice) => {
    setIsLoading(true);
    setError(null);
    try {
      const { data, error: sessionError } = await tenantFetch<VoiceSession>('/v1/voice/sessions', {
        method: 'POST',
        body: JSON.stringify({
          voice: voice.id,
          workspace_id: codebaseId,
          session_id: sessionId,
          mode: mode,
          playback_style: playbackStyle,
        }),
      });
      if (sessionError || !data?.access_token || !data.livekit_url || !data.room_name || !data.user_id) {
        throw new Error(sessionError || 'Voice server returned an incomplete connection');
      }
      setConnectionInfo(data);
      setIsOpen(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start voice session');
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
      // Check for secure context (mediaDevices requires HTTPS or localhost)
      if (typeof navigator !== 'undefined' && !navigator.mediaDevices) {
        alert('Voice chat requires a secure connection (HTTPS). Please access this page via HTTPS or localhost.');
        return;
      }
      if (!selectedVoice) {
        setShowVoiceSelector(true);
      } else {
        await startSession(selectedVoice);
      }
    } else if (mode === 'playback' && sessionId) {
      setIsOpen(true);
    }
  };

  const handleClose = async () => {
    const room = connectionInfo?.room_name;
    setIsOpen(false);
    setConnectionInfo(null);
    if (room) {
      try {
        const { error: cleanupError } = await tenantFetch(`/v1/voice/sessions/${encodeURIComponent(room)}`, {
          method: 'DELETE',
        });
        if (cleanupError) setError(`Could not end voice session: ${cleanupError}`);
      } catch (e) {
        setError(`Could not end voice session: ${e instanceof Error ? e.message : String(e)}`);
      }
    }
  };

  return (
    <>
      <button
        onClick={handleClick}
        disabled={isLoading}
        className={compact
          ? 'inline-flex items-center justify-center rounded-full bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 transition-colors p-2'
          : 'flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors'
        }
        aria-label={isLoading ? 'Connecting voice...' : mode === 'chat' ? 'Voice Chat' : 'Playback Session'}
        title={mode === 'chat' ? 'Voice Chat' : 'Playback Session'}
      >
        <MicIcon className={compact ? 'w-4 h-4' : 'w-4 h-4'} />
        {!compact && (
          <span>{isLoading ? 'Connecting...' : mode === 'chat' ? 'Voice Chat' : 'Playback Session'}</span>
        )}
      </button>

      {error && <p role="alert" className="text-sm text-red-600 dark:text-red-400">{error}</p>}
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
          userId={connectionInfo.user_id}
          onClose={handleClose}
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