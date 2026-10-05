'use client';

import { useState, useEffect } from 'react';

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

const PhoneOffIcon = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M16 8l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2M5 3a2 2 0 00-2 2v1c0 8.284 6.716 15 15 15h1a2 2 0 002-2v-3.28a1 1 0 00-.684-.948l-4.493-1.498a1 1 0 00-1.21.502l-1.13 2.257a11.042 11.042 0 01-5.516-5.517l2.257-1.128a1 1 0 00.502-1.21L9.228 3.683A1 1 0 008.279 3H5z" />
  </svg>
);

const VolumeIcon = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
  </svg>
);

interface VoiceAssistantUIProps {
  voice: { id: string; name: string; description: string };
  onClose: () => void;
}

type AgentState = 'idle' | 'listening' | 'thinking' | 'speaking';

const stateMessages: Record<AgentState, string> = {
  idle: 'Ready to help',
  listening: 'Listening...',
  thinking: 'Processing...',
  speaking: 'Speaking...',
};

export default function VoiceAssistantUI({ voice, onClose }: VoiceAssistantUIProps) {
  const [isMuted, setIsMuted] = useState(false);
  const [agentState, setAgentState] = useState<AgentState>('idle');
  const [audioLevel, setAudioLevel] = useState(0);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    const timer = setInterval(() => {
      setAudioLevel(Math.random() * 0.5 + (agentState === 'speaking' ? 0.3 : 0));
    }, 100);
    return () => clearInterval(timer);
  }, [agentState]);

  useEffect(() => {
    setIsConnected(true);
  }, []);

  const toggleMute = () => {
    setIsMuted(!isMuted);
  };

  const handleEndCall = () => {
    onClose();
  };

  const getStateColor = () => {
    switch (agentState) {
      case 'listening':
        return 'text-blue-600 bg-blue-100';
      case 'thinking':
        return 'text-yellow-600 bg-yellow-100';
      case 'speaking':
        return 'text-green-600 bg-green-100';
      default:
        return 'text-gray-600 bg-gray-100';
    }
  };

  return (
    <div className="flex flex-col items-center py-8">
      <div className="relative mb-8">
        <div
          className={`w-32 h-32 rounded-full flex items-center justify-center transition-all duration-300 ${
            agentState === 'speaking'
              ? 'bg-gradient-to-br from-green-400 to-green-600 animate-pulse'
              : agentState === 'listening'
              ? 'bg-gradient-to-br from-blue-400 to-blue-600 animate-pulse'
              : agentState === 'thinking'
              ? 'bg-gradient-to-br from-yellow-400 to-yellow-600'
              : 'bg-gradient-to-br from-gray-400 to-gray-600'
          }`}
        >
          <VolumeIcon className="w-16 h-16 text-white" />
        </div>

        <div className="absolute -bottom-2 left-1/2 -translate-x-1/2 bg-white dark:bg-gray-800 px-3 py-1 rounded-full shadow-md">
          <span className={`text-xs font-medium px-2 py-1 rounded-full ${getStateColor()}`}>
            {stateMessages[agentState]}
          </span>
        </div>
      </div>

      <div className="w-full max-w-xs mb-8">
        <div className="flex items-end justify-center gap-1 h-16">
          {[...Array(20)].map((_, i) => {
            const height = Math.max(4, audioLevel * 100 * Math.sin((i / 20) * Math.PI));
            return (
              <div
                key={i}
                className="w-2 bg-gradient-to-t from-blue-500 to-indigo-500 rounded-t transition-all duration-75"
                style={{ height: `${height}%` }}
              />
            );
          })}
        </div>
      </div>

      <div className="text-center mb-8">
        <p className="text-lg font-medium">{voice.name}</p>
        <p className="text-sm text-gray-500 dark:text-gray-400">{voice.description}</p>
      </div>

      <div className="flex items-center gap-4">
        <button
          onClick={toggleMute}
          className={`p-4 rounded-full transition-all ${
            isMuted
              ? 'bg-red-100 text-red-600 hover:bg-red-200'
              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
          }`}
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

      <div className="mt-6 flex items-center gap-2 text-sm text-gray-500">
        <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
        <span>{isConnected ? 'Connected to LiveKit' : 'Connecting...'}</span>
      </div>
    </div>
  );
}
