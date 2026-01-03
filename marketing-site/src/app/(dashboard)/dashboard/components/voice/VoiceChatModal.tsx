'use client';

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

const VolumeIcon = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
  </svg>
);

interface VoiceChatModalProps {
  token: string;
  serverUrl: string;
  roomName: string;
  voice: { id: string; name: string; description: string };
  sessionId?: string;
  onClose: () => void;
  children?: React.ReactNode;
}

export default function VoiceChatModal({
  token,
  serverUrl,
  roomName,
  voice,
  sessionId,
  onClose,
  children,
}: VoiceChatModalProps) {
  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-2xl overflow-hidden">
        <div className="flex items-center justify-between p-4 bg-gradient-to-r from-blue-600 to-indigo-600">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-white/20 rounded-lg">
              <VolumeIcon className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-white font-semibold">Voice Assistant</h2>
              <p className="text-white/80 text-sm">Voice: {voice.name}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-white/20 rounded-full transition-colors"
          >
            <CloseIcon className="w-5 h-5 text-white" />
          </button>
        </div>

        <div className="p-6">
          {children ? (
            children
          ) : (
            <div className="flex flex-col items-center justify-center py-12">
              <div className="relative mb-6">
                <div className="w-24 h-24 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center">
                  <MicIcon className="w-12 h-12 text-white" />
                </div>
                <div className="absolute -bottom-1 -right-1 bg-green-500 w-6 h-6 rounded-full border-4 border-white dark:border-gray-900 flex items-center justify-center">
                  <div className="w-2 h-2 bg-white rounded-full animate-pulse" />
                </div>
              </div>

              <h3 className="text-xl font-semibold mb-2">Connecting to Voice Session</h3>
              <p className="text-gray-500 dark:text-gray-400 text-center max-w-sm">
                Setting up your LiveKit connection for real-time voice interaction with the agent.
              </p>

              <div className="mt-8 w-full max-w-xs">
                <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-blue-500 to-indigo-600 animate-pulse w-2/3" />
                </div>
                <p className="text-sm text-gray-500 mt-2 text-center">Connecting...</p>
              </div>
            </div>
          )}
        </div>

        <div className="px-6 py-4 bg-gray-50 dark:bg-gray-800/50 border-t dark:border-gray-700">
          <div className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-2 text-gray-500">
              <div className="w-2 h-2 bg-green-500 rounded-full" />
              <span>LiveKit Connected</span>
            </div>
            <div className="flex items-center gap-4 text-gray-400">
              {sessionId && (
                <span className="font-mono text-xs">Session: {sessionId.slice(0, 8)}...</span>
              )}
              <span>Room: {roomName || 'N/A'}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
