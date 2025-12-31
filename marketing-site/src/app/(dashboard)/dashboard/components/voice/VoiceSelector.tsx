'use client';

import { useState, useEffect } from 'react';

const CloseIcon = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
  </svg>
);

const VolumeIcon = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
  </svg>
);

interface VoiceSelectorProps {
  selected: { id: string; name: string; description: string } | null;
  onSelect: (voice: { id: string; name: string; description: string }) => void;
  onClose: () => void;
}

interface Voice {
  id: string;
  name: string;
  description: string;
}

export default function VoiceSelector({ selected, onSelect, onClose }: VoiceSelectorProps) {
  const [voices, setVoices] = useState<Voice[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [previewVoice, setPreviewVoice] = useState<string | null>(null);

  const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || '';

  useEffect(() => {
    const loadVoices = async () => {
      setIsLoading(true);
      try {
        const response = await fetch(`${apiBaseUrl}/v1/voice/voices`);
        if (response.ok) {
          const data = await response.json();
          setVoices(data);
        }
      } catch {
        console.error('Failed to load voices');
      } finally {
        setIsLoading(false);
      }
    };
    loadVoices();
  }, [apiBaseUrl]);

  const handlePreview = (voiceId: string) => {
    setPreviewVoice(voiceId);
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-full max-w-md mx-4">
        <div className="flex items-center justify-between p-4 border-b dark:border-gray-700">
          <h2 className="text-lg font-semibold">Select Voice</h2>
          <button
            onClick={onClose}
            className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-full transition-colors"
          >
            <CloseIcon className="w-5 h-5" />
          </button>
        </div>

        <div className="p-4 max-h-96 overflow-y-auto">
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            </div>
          ) : voices.length === 0 ? (
            <p className="text-center text-gray-500 py-8">No voices available</p>
          ) : (
            <div className="space-y-2">
              {voices.map((voice) => (
                <button
                  key={voice.id}
                  onClick={() => onSelect(voice)}
                  onMouseEnter={() => handlePreview(voice.id)}
                  onMouseLeave={() => setPreviewVoice(null)}
                  className={`w-full p-3 rounded-lg text-left transition-all ${
                    selected?.id === voice.id
                      ? 'bg-blue-50 dark:bg-blue-900/20 border-2 border-blue-500'
                      : 'bg-gray-50 dark:bg-gray-700/50 border-2 border-transparent hover:border-blue-300'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <VolumeIcon className="w-5 h-5 text-blue-600 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="font-medium truncate">{voice.name}</p>
                      <p className="text-sm text-gray-500 dark:text-gray-400 truncate">
                        {voice.description}
                      </p>
                    </div>
                    {selected?.id === voice.id && (
                      <div className="w-3 h-3 bg-blue-600 rounded-full flex-shrink-0" />
                    )}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="p-4 border-t dark:border-gray-700">
          <button
            onClick={onClose}
            className="w-full px-4 py-2 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-lg transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
