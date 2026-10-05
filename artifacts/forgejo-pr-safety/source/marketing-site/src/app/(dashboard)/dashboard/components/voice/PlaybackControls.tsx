'use client';

import { useState } from 'react';

// SVG Icons
const PlayIcon = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
    <path strokeLinecap="round" strokeLinejoin="round" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

const FileTextIcon = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
  </svg>
);

interface PlaybackControlsProps {
  sessionId: string;
  onPlayback: (mode: 'verbatim' | 'summary') => void;
}

type PlaybackMode = 'verbatim' | 'summary';

export default function PlaybackControls({ sessionId, onPlayback }: PlaybackControlsProps) {
  const [playbackMode, setPlaybackMode] = useState<PlaybackMode>('verbatim');
  const [isPlaying, setIsPlaying] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const handleStartPlayback = async () => {
    setIsLoading(true);
    setIsPlaying(true);
    try {
      onPlayback(playbackMode);
    } finally {
      setIsLoading(false);
    }
  };

  const handleStopPlayback = () => {
    setIsPlaying(false);
  };

  return (
    <div className="flex flex-col items-center py-8">
      <div className="w-full max-w-sm">
        <div className="mb-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <FileTextIcon className="w-5 h-5" />
            Session Playback
          </h3>
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
            Session ID: <span className="font-mono text-xs bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded">{sessionId}</span>
          </p>
        </div>

        <div className="space-y-3 mb-6">
          <label className="block text-sm font-medium mb-2">Playback Mode</label>
          
          <label
            className={`flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-all ${
              playbackMode === 'verbatim'
                ? 'bg-blue-50 dark:bg-blue-900/20 border-2 border-blue-500'
                : 'bg-gray-50 dark:bg-gray-700/50 border-2 border-transparent hover:border-gray-300'
            }`}
          >
            <input
              type="radio"
              name="playbackMode"
              value="verbatim"
              checked={playbackMode === 'verbatim'}
              onChange={() => setPlaybackMode('verbatim')}
              className="sr-only"
            />
            <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${
              playbackMode === 'verbatim' ? 'border-blue-600' : 'border-gray-400'
            }`}>
              {playbackMode === 'verbatim' && (
                <div className="w-2 h-2 rounded-full bg-blue-600" />
              )}
            </div>
            <div className="flex-1">
              <p className="font-medium">Verbatim</p>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Play back the full conversation as recorded
              </p>
            </div>
          </label>

          <label
            className={`flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-all ${
              playbackMode === 'summary'
                ? 'bg-blue-50 dark:bg-blue-900/20 border-2 border-blue-500'
                : 'bg-gray-50 dark:bg-gray-700/50 border-2 border-transparent hover:border-gray-300'
            }`}
          >
            <input
              type="radio"
              name="playbackMode"
              value="summary"
              checked={playbackMode === 'summary'}
              onChange={() => setPlaybackMode('summary')}
              className="sr-only"
            />
            <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${
              playbackMode === 'summary' ? 'border-blue-600' : 'border-gray-400'
            }`}>
              {playbackMode === 'summary' && (
                <div className="w-2 h-2 rounded-full bg-blue-600" />
              )}
            </div>
            <div className="flex-1">
              <p className="font-medium">Summary</p>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Play back an AI-generated summary of the conversation
              </p>
            </div>
          </label>
        </div>

        <button
          onClick={isPlaying ? handleStopPlayback : handleStartPlayback}
          disabled={isLoading}
          className={`w-full flex items-center justify-center gap-2 py-3 px-4 rounded-lg font-medium transition-all ${
            isPlaying
              ? 'bg-red-100 text-red-600 hover:bg-red-200'
              : 'bg-blue-600 text-white hover:bg-blue-700'
          } disabled:opacity-50`}
        >
          {isLoading ? (
            <div className="w-5 h-5 border-2 border-current border-t-transparent rounded-full animate-spin" />
          ) : (
            <>
              <PlayIcon className="w-5 h-5" />
              {isPlaying ? 'Stop Playback' : 'Start Playback'}
            </>
          )}
        </button>

        {isPlaying && (
          <div className="mt-4 p-3 bg-green-50 dark:bg-green-900/20 rounded-lg">
            <p className="text-sm text-green-700 dark:text-green-400 flex items-center gap-2">
              <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
              Playing back session...
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
