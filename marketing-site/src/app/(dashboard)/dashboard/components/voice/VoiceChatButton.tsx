'use client';

import { useState } from 'react';

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
}: VoiceChatButtonProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [selectedVoice, setSelectedVoice] = useState<Voice | null>(null);
  const [connectionInfo, setConnectionInfo] = useState<VoiceSession | null>(null);
  const [showVoiceSelector, setShowVoiceSelector] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || '';

  const fetchVoices = async () => {
    try {
      const response = await fetch(`${apiBaseUrl}/v1/voice/voices`);
      if (response.ok) {
        return await response.json();
      }
      return [];
    } catch {
      return [];
    }
  };

  const startSession = async (voice: Voice) => {
    setIsLoading(true);
    try {
      const response = await fetch(`${apiBaseUrl}/v1/voice/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          voice: voice.id,
          codebase_id: codebaseId,
          session_id: sessionId,
        }),
      });
      if (response.ok) {
        const session = await response.json();
        setConnectionInfo(session);
        setIsOpen(true);
      } else {
        const error = await response.json();
        console.error('Failed to start voice session:', error);
      }
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
