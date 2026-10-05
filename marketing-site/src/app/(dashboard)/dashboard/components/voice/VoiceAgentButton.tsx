'use client';

import { useState, useCallback } from 'react';
import { useTenantApi } from '@/hooks/useTenantApi';
import VoiceChatModal from './VoiceChatModal';

interface VoiceChoice { id: string; name: string; description: string }

type DeployState = 'idle' | 'deploying' | 'waiting' | 'error';
type SessionState = 'idle' | 'creating' | 'error';

/** Response from POST /v1/voice/sessions (Python REST). */
interface VoiceSessionResponse {
    room_name: string;
    access_token: string;
    livekit_url: string;
    voice: string;
    mode: string;
    expires_at: string;
    user_id: string;
}

interface VoiceAgentButtonProps {
    codebaseId?: string;
    workers: Array<{
        worker_id: string;
        name: string;
        is_sse_connected?: boolean;
        last_seen?: string;
    }>;
    onWorkerDeployed?: () => void;
}

const MicIcon = ({ className }: { className?: string }) => (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
    </svg>
);

const SpinnerIcon = ({ className }: { className?: string }) => (
    <svg className={`${className} animate-spin`} fill="none" viewBox="0 0 24 24">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
    </svg>
);

const RocketIcon = ({ className }: { className?: string }) => (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M15.59 14.37a6 6 0 01-5.84 7.38v-4.8m5.84-2.58a14.98 14.98 0 006.16-12.12A14.98 14.98 0 009.631 8.41m5.96 5.96a14.926 14.926 0 01-5.841 2.58m-.119-8.54a6 6 0 00-7.381 5.84h4.8m2.581-5.84a14.927 14.927 0 00-2.58 5.84m2.699 2.7c-.103.021-.207.041-.311.06a15.09 15.09 0 01-2.448-2.448 14.9 14.9 0 01.06-.312m-2.24 2.39a4.493 4.493 0 00-6.233 0c-2.646.749-5.479 0-5.479-4.726 0-1.257.484-2.467 1.348-3.369.866-.902 2.04-1.405 3.27-1.405l1.91 1.91M18 13l-4-4" />
    </svg>
);

export default function VoiceAgentButton({ codebaseId, workers, onWorkerDeployed }: VoiceAgentButtonProps) {
    const { tenantFetch } = useTenantApi();

    const [deployState, setDeployState] = useState<DeployState>('idle');
    const [sessionState, setSessionState] = useState<SessionState>('idle');
    const [error, setError] = useState<string | null>(null);
    const [modalOpen, setModalOpen] = useState(false);
    const [connectionInfo, setConnectionInfo] = useState<{
        token: string;
        serverUrl: string;
        roomName: string;
        voice: VoiceChoice;
        userId: string;
    } | null>(null);

    const hasOnlineWorker = workers.some(w => w.is_sse_connected);

    const deployWorker = useCallback(async (): Promise<boolean> => {
        setDeployState('deploying');
        setError(null);
        try {
            const subagentId = `voice-worker-${Date.now()}`;
            const resp = await tenantFetch<{ action?: string; pod_name?: string }>('/v1/k8s/subagent', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    subagent_id: subagentId,
                    env_vars: {
                        A2A_CODEBASE_ID: codebaseId ?? '',
                        CODETETHER_WORKER_NAME: subagentId,
                        CODETETHER_LOG_LEVEL: 'info',
                    },
                }),
            });
            if (resp.error) {
                setError(resp.error);
                setDeployState('error');
                return false;
            }

            setDeployState('waiting');
            for (let i = 0; i < 30; i++) {
                await new Promise(r => setTimeout(r, 2000));
                // This endpoint contains only live SSE connections, not the merged worker inventory.
                const check = await tenantFetch<{ workers?: Array<{ worker_id?: string; agent_name?: string }> }>('/v1/worker/connected');
                if (check.error) throw new Error(`Could not check worker readiness: ${check.error}`);
                if (check.data?.workers?.some(worker =>
                    worker.agent_name === subagentId)) {
                    setDeployState('idle');
                    onWorkerDeployed?.();
                    return true;
                }
            }
            setError('Worker deployed but did not come online within 60s');
            setDeployState('error');
            return false;
        } catch (err) {
            setError(err instanceof Error ? err.message : String(err));
            setDeployState('error');
            return false;
        }
    }, [codebaseId, tenantFetch, onWorkerDeployed]);

    /**
     * Create a voice session via the Python REST API.
     * POST /v1/voice/sessions creates a LiveKit room, dispatches the voice agent
     * worker into it, and returns an access token for the user to join.
     */
    const createVoiceSession = useCallback(async (): Promise<(VoiceSessionResponse & { selectedVoice: VoiceChoice }) | null> => {
        setSessionState('creating');
        setError(null);
        try {
            const catalog = await tenantFetch<{ voices: VoiceChoice[] }>('/v1/voice/voices');
            const selectedVoice = catalog.data?.voices?.[0];
            if (catalog.error || !selectedVoice) {
                throw new Error(catalog.error || 'No voice is configured on this server');
            }
            const resp = await tenantFetch<VoiceSessionResponse>('/v1/voice/sessions', {
                method: 'POST',
                body: JSON.stringify({
                    voice: selectedVoice.id,
                    mode: 'chat',
                    workspace_id: codebaseId ?? null,
                }),
            });
            if (resp.error || !resp.data) {
                setError(resp.error || 'Failed to create voice session');
                setSessionState('error');
                return null;
            }
            if (!resp.data.access_token || !resp.data.livekit_url || !resp.data.room_name || !resp.data.user_id) {
                throw new Error('Voice server returned an incomplete connection');
            }
            setSessionState('idle');
            return { ...resp.data, selectedVoice };
        } catch (err) {
            setError(err instanceof Error ? err.message : String(err));
            setSessionState('error');
            return null;
        }
    }, [codebaseId, tenantFetch]);

    const handleClick = useCallback(async () => {
        // Check for secure context (mic requires HTTPS or localhost)
        if (typeof navigator !== 'undefined' && !navigator.mediaDevices) {
            alert('Voice chat requires a secure connection (HTTPS or localhost).');
            return;
        }

        // If no worker online, offer to deploy one
        if (!hasOnlineWorker) {
            const shouldDeploy = confirm(
                'No worker agents are currently online. Deploy a CodeTether worker agent to the cluster?\n\nThis will start a worker pod that can execute tasks.'
            );
            if (!shouldDeploy) return;
            const deployed = await deployWorker();
            if (!deployed) return;
        }

        // Create voice session → LiveKit room + agent dispatch (Python REST)
        const voiceSession = await createVoiceSession();
        if (!voiceSession) return;

        setConnectionInfo({
            token: voiceSession.access_token,
            serverUrl: voiceSession.livekit_url,
            roomName: voiceSession.room_name,
            voice: voiceSession.selectedVoice,
            userId: voiceSession.user_id,
        });
        setModalOpen(true);
    }, [hasOnlineWorker, deployWorker, createVoiceSession]);

    const handleClose = useCallback(async () => {
        const roomName = connectionInfo?.roomName;
        setModalOpen(false);
        setConnectionInfo(null);
        setDeployState('idle');
        setSessionState('idle');
        setError(null);
        if (roomName) {
            try {
                const result = await tenantFetch('/v1/voice/sessions/' + encodeURIComponent(roomName), { method: 'DELETE' });
                if (result.error) setError('Could not end voice session: ' + result.error);
            } catch (err) {
                setError('Could not end voice session: ' + (err instanceof Error ? err.message : String(err)));
            }
        }
    }, [connectionInfo, tenantFetch]);

    const isLoading = sessionState === 'creating' || deployState === 'deploying' || deployState === 'waiting';

    const getButtonContent = () => {
        if (deployState === 'deploying') return { icon: <SpinnerIcon className="w-5 h-5" />, text: 'Deploying Worker...' };
        if (deployState === 'waiting') return { icon: <SpinnerIcon className="w-5 h-5" />, text: 'Waiting for Worker...' };
        if (sessionState === 'creating') return { icon: <SpinnerIcon className="w-5 h-5" />, text: 'Connecting...' };
        if (!hasOnlineWorker) return { icon: <RocketIcon className="w-5 h-5" />, text: 'Talk to Agent (Deploy Worker)' };
        return { icon: <MicIcon className="w-5 h-5" />, text: 'Talk to Agent' };
    };

    const { icon, text } = getButtonContent();

    return (
        <>
            <button
                onClick={handleClick}
                disabled={isLoading}
                className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-gradient-to-r from-indigo-600 to-purple-600 text-white rounded-lg hover:from-indigo-500 hover:to-purple-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-md hover:shadow-lg font-medium"
                aria-label={text}
            >
                {icon}
                <span>{text}</span>
            </button>

            {error && (
                <p className="mt-1 text-xs text-red-500 dark:text-red-400">
                    {error}
                </p>
            )}

            {!hasOnlineWorker && deployState === 'idle' && (
                <p className="mt-1 text-xs text-amber-600 dark:text-amber-400">
                    No workers online — a worker will be deployed when you click.
                </p>
            )}

            {modalOpen && connectionInfo && (
                <VoiceChatModal
                    token={connectionInfo.token}
                    serverUrl={connectionInfo.serverUrl}
                    roomName={connectionInfo.roomName}
                    voice={connectionInfo.voice}
                    userId={connectionInfo.userId}
                    onClose={handleClose}
                />
            )}
        </>
    );
}