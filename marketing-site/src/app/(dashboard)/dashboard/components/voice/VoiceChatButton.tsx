'use client';

import { useEffect, useMemo, useState } from 'react';
import { useSession } from 'next-auth/react';
import { useWorkers } from '@/components/WorkerSelector';
import { useTenantApi } from '@/hooks/useTenantApi';
import VoiceSelector from './VoiceSelector';
import VoiceChatModal from './VoiceChatModal';
import PlaybackControls from './PlaybackControls';

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
  compact?: boolean;
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

interface WorkspaceOption {
  id: string;
  name: string;
  path: string;
  worker_id?: string | null;
}

function normalizeWorkspaceOptions(data: unknown): WorkspaceOption[] {
  const items = Array.isArray(data)
    ? data
    : Array.isArray((data as { workspaces?: unknown[] } | undefined)?.workspaces)
      ? (data as { workspaces: unknown[] }).workspaces
      : Array.isArray((data as { codebases?: unknown[] } | undefined)?.codebases)
        ? (data as { codebases: unknown[] }).codebases
        : Array.isArray((data as { data?: unknown[] } | undefined)?.data)
          ? (data as { data: unknown[] }).data
          : [];

  return items
    .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object')
    .map((item) => ({
      id: String(item.id ?? ''),
      name: String(item.name ?? item.id ?? ''),
      path: String(item.path ?? ''),
      worker_id: typeof item.worker_id === 'string' ? item.worker_id : null,
    }))
    .filter((item) => item.id);
}

function formatWorkerLabel(worker: { worker_id: string; name?: string }): string {
  return (worker.name || worker.worker_id).trim();
}

function formatWorkspaceLabel(workspace: WorkspaceOption): string {
  const leaf = workspace.path.split('/').filter(Boolean).pop();
  const suffix = leaf && leaf !== workspace.name ? ` (${leaf})` : '';
  return `${workspace.name}${suffix}`;
}

export default function VoiceChatButton({
  codebaseId,
  sessionId,
  mode,
  playbackStyle = 'verbatim',
  compact = false,
}: VoiceChatButtonProps) {
  const { data: session } = useSession();
  const { tenantFetch } = useTenantApi();
  const [isOpen, setIsOpen] = useState(false);
  const [selectedVoice, setSelectedVoice] = useState<Voice | null>(null);
  const [connectionInfo, setConnectionInfo] = useState<VoiceSession | null>(null);
  const [showVoiceSelector, setShowVoiceSelector] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedWorkerId, setSelectedWorkerId] = useState('');
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState(codebaseId ?? '');
  const [workspaces, setWorkspaces] = useState<WorkspaceOption[]>([]);
  const [workspacesLoading, setWorkspacesLoading] = useState(false);
  const [workspacesError, setWorkspacesError] = useState<string | null>(null);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const { workers, loading: workersLoading, error: workersError } = useWorkers(showVoiceSelector && mode === 'chat');

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

  const connectedWorkers = useMemo(
    () => workers.filter((worker) => worker.is_sse_connected),
    [workers]
  );

  const selectedWorker = useMemo(
    () => connectedWorkers.find((worker) => worker.worker_id === selectedWorkerId) || null,
    [connectedWorkers, selectedWorkerId]
  );

  const workerScopedWorkspaces = useMemo(() => {
    if (!selectedWorkerId) return [];

    const assignedWorkspaceIds = new Set(selectedWorker?.codebases || []);
    return workspaces.filter(
      (workspace) =>
        workspace.worker_id === selectedWorkerId || assignedWorkspaceIds.has(workspace.id)
    );
  }, [selectedWorker, selectedWorkerId, workspaces]);

  useEffect(() => {
    if (!showVoiceSelector || mode !== 'chat') return;

    let cancelled = false;

    const loadWorkspaces = async () => {
      setWorkspacesLoading(true);
      try {
        const response = await tenantFetch('/v1/agent/workspaces/list');
        if (response.error) {
          throw new Error(response.error);
        }

        if (!cancelled) {
          setWorkspaces(normalizeWorkspaceOptions(response.data));
          setWorkspacesError(null);
        }
      } catch (error) {
        if (!cancelled) {
          setWorkspaces([]);
          setWorkspacesError(
            error instanceof Error ? error.message : 'Failed to load workspaces'
          );
        }
      } finally {
        if (!cancelled) {
          setWorkspacesLoading(false);
        }
      }
    };

    void loadWorkspaces();

    return () => {
      cancelled = true;
    };
  }, [mode, showVoiceSelector, tenantFetch]);

  useEffect(() => {
    if (!showVoiceSelector) return;

    if (!selectedWorkerId) {
      setSelectedWorkspaceId(codebaseId ?? '');
      return;
    }

    if (!connectedWorkers.some((worker) => worker.worker_id === selectedWorkerId)) {
      setSelectedWorkerId('');
      return;
    }

    const preferredWorkspaceId =
      workerScopedWorkspaces.find((workspace) => workspace.id === selectedWorkspaceId)?.id ||
      workerScopedWorkspaces.find((workspace) => workspace.id === codebaseId)?.id ||
      workerScopedWorkspaces[0]?.id ||
      '';

    if (preferredWorkspaceId !== selectedWorkspaceId) {
      setSelectedWorkspaceId(preferredWorkspaceId);
    }
  }, [
    codebaseId,
    connectedWorkers,
    selectedWorkerId,
    selectedWorkspaceId,
    showVoiceSelector,
    workerScopedWorkspaces,
  ]);

  const startSession = async (voice: Voice) => {
    const targetWorkspaceId = selectedWorkerId
      ? selectedWorkspaceId || null
      : codebaseId || null;

    if (selectedWorkerId && !targetWorkspaceId) {
      setSessionError('Select a workspace registered on the chosen worker before starting voice chat.');
      return false;
    }

    setIsLoading(true);
    setSessionError(null);

    try {
      const response = await tenantFetch<VoiceSession>('/v1/voice/sessions', {
        method: 'POST',
        body: JSON.stringify({
          voice: voice.id,
          workspace_id: targetWorkspaceId,
          worker_id: selectedWorkerId || null,
          session_id: sessionId,
          mode,
          playback_style: playbackStyle,
          user_id: userId,
        }),
      });

      if (response.error || !response.data) {
        throw new Error(response.error || 'Failed to start voice session');
      }

      setConnectionInfo(response.data);
      setIsOpen(true);
      return true;
    } catch (e) {
      console.error('Failed to start voice session:', e);
      setSessionError(
        e instanceof Error ? e.message : 'Failed to start voice session'
      );
      return false;
    } finally {
      setIsLoading(false);
    }
  };

  const handleVoiceSelect = async (voice: Voice) => {
    setSelectedVoice(voice);
    // Start session immediately after voice selection
    const started = await startSession(voice);
    if (started) {
      setShowVoiceSelector(false);
    }
  };

  const handleClick = async () => {
    if (mode === 'chat') {
      // Check for secure context (mediaDevices requires HTTPS or localhost)
      if (typeof navigator !== 'undefined' && !navigator.mediaDevices) {
        alert('Voice chat requires a secure connection (HTTPS). Please access this page via HTTPS or localhost.');
        return;
      }
      setSessionError(null);
      setShowVoiceSelector(true);
    } else if (mode === 'playback' && sessionId) {
      setIsOpen(true);
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

      {showVoiceSelector && (
        <VoiceSelector
          selected={selectedVoice}
          onSelect={handleVoiceSelect}
          onClose={() => {
            setShowVoiceSelector(false);
            setSessionError(null);
          }}
        >
          <div className="space-y-3">
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">
                Worker
              </label>
              <select
                value={selectedWorkerId}
                onChange={(event) => setSelectedWorkerId(event.target.value)}
                className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
              >
                <option value="">Auto routing (current workspace)</option>
                {connectedWorkers.map((worker) => (
                  <option key={worker.worker_id} value={worker.worker_id}>
                    {formatWorkerLabel(worker)}
                  </option>
                ))}
              </select>
            </div>

            {selectedWorkerId ? (
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">
                  Workspace
                </label>
                <select
                  value={selectedWorkspaceId}
                  onChange={(event) => setSelectedWorkspaceId(event.target.value)}
                  disabled={workspacesLoading || workerScopedWorkspaces.length === 0}
                  className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:ring-2 focus:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-60 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
                >
                  {workerScopedWorkspaces.length === 0 ? (
                    <option value="">No registered workspaces for this worker</option>
                  ) : (
                    workerScopedWorkspaces.map((workspace) => (
                      <option key={workspace.id} value={workspace.id}>
                        {formatWorkspaceLabel(workspace)}
                      </option>
                    ))
                  )}
                </select>
              </div>
            ) : (
              <p className="text-xs text-gray-500 dark:text-gray-400">
                {codebaseId
                  ? `Using the current workspace by default: ${codebaseId}`
                  : 'Using global context by default.'}
              </p>
            )}

            {workersError ? (
              <p className="text-xs text-red-500">{workersError}</p>
            ) : null}
            {workspacesError ? (
              <p className="text-xs text-red-500">{workspacesError}</p>
            ) : null}
            {selectedWorkerId && !workersLoading && !workspacesLoading && workerScopedWorkspaces.length === 0 ? (
              <p className="text-xs text-amber-600 dark:text-amber-400">
                The selected worker does not have a registered workspace available for this voice session.
              </p>
            ) : null}
            {sessionError ? (
              <p className="text-xs text-red-500">{sessionError}</p>
            ) : null}
          </div>
        </VoiceSelector>
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
