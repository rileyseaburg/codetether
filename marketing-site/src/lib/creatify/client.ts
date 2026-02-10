/**
 * Creatify AI Video Generation Client (TypeScript)
 *
 * Generates video ads from URLs or product details using Creatify's API.
 * Port of a2a_server/creatify_video.py for use in the Next.js marketing site.
 *
 * API Docs: https://docs.creatify.ai/api-reference
 *
 * @module lib/creatify/client
 */

const CREATIFY_API_BASE = 'https://api.creatify.ai/api';

function getCredentials() {
    const apiKey = process.env.CREATIFY_API_KEY;
    if (!apiKey) throw new Error('CREATIFY_API_KEY environment variable not set');

    // Creatify uses "API_ID:API_KEY" format
    const [apiId, apiSecret] = apiKey.includes(':')
        ? apiKey.split(':')
        : [apiKey, apiKey];

    return { apiId, apiSecret };
}

async function creatifyFetch<T = unknown>(
    path: string,
    options: { method?: string; body?: unknown } = {},
): Promise<T> {
    const { apiId, apiSecret } = getCredentials();

    const res = await fetch(`${CREATIFY_API_BASE}${path}`, {
        method: options.method ?? 'GET',
        headers: {
            'X-API-ID': apiId,
            'X-API-KEY': apiSecret,
            'Content-Type': 'application/json',
        },
        ...(options.body ? { body: JSON.stringify(options.body) } : {}),
    });

    if (!res.ok) {
        const text = await res.text().catch(() => '');
        throw new Error(`Creatify API ${res.status}: ${text}`);
    }

    return res.json() as Promise<T>;
}

// ============================================================================
// Types
// ============================================================================

export type VideoStatus = 'pending' | 'processing' | 'done' | 'failed';
export type AspectRatio = '9:16' | '16:9' | '1:1';

export interface VideoResult {
    id: string;
    status: VideoStatus;
    video_url?: string;
    preview_url?: string;
    thumbnail_url?: string;
    duration?: number;
    credits_used?: number;
    error?: string;
}

export interface LinkResult {
    id: string;
    [key: string]: unknown;
}

// ============================================================================
// Link Creation (Step 1)
// ============================================================================

/** Analyze a URL and create a link for video generation. Cost: 1 credit. */
export async function createLink(url: string): Promise<LinkResult> {
    return creatifyFetch<LinkResult>('/links', {
        method: 'POST',
        body: { url },
    });
}

/** Create a link from custom product details (no URL scraping). Cost: 1 credit. */
export async function createLinkWithParams(params: {
    productName: string;
    productDescription: string;
    mediaUrls: string[];
    logoUrl?: string;
}): Promise<LinkResult> {
    return creatifyFetch<LinkResult>('/link_with_params', {
        method: 'POST',
        body: {
            product_name: params.productName,
            product_description: params.productDescription,
            media_urls: params.mediaUrls,
            ...(params.logoUrl ? { logo_url: params.logoUrl } : {}),
        },
    });
}

// ============================================================================
// Video Generation (Step 2)
// ============================================================================

/** Generate a video from a link. Cost: 5 credits per 30s. */
export async function createVideo(params: {
    linkId: string;
    aspectRatio?: AspectRatio;
    voiceId?: string;
    avatarId?: string;
    script?: string;
    style?: string;
}): Promise<VideoResult> {
    const body: Record<string, unknown> = {
        link_id: params.linkId,
        aspect_ratio: params.aspectRatio ?? '16:9',
    };
    if (params.voiceId) body.voice_id = params.voiceId;
    if (params.avatarId) body.avatar_id = params.avatarId;
    if (params.script) body.script = params.script;
    if (params.style) body.style = params.style;

    return creatifyFetch<VideoResult>('/link_to_videos', {
        method: 'POST',
        body,
    });
}

// ============================================================================
// Status Polling (Step 3)
// ============================================================================

/** Get a video's current status and result. */
export async function getVideo(videoId: string): Promise<VideoResult> {
    return creatifyFetch<VideoResult>(`/link_to_videos/${videoId}`);
}

/** Poll until video is done, failed, or timeout. */
export async function waitForVideo(
    videoId: string,
    pollIntervalMs = 10_000,
    maxWaitMs = 300_000,
): Promise<VideoResult> {
    const start = Date.now();

    while (Date.now() - start < maxWaitMs) {
        const result = await getVideo(videoId);

        if (result.status === 'done' || result.status === 'failed') {
            return result;
        }

        await new Promise((r) => setTimeout(r, pollIntervalMs));
    }

    return {
        id: videoId,
        status: 'processing',
        error: `Video still processing after ${maxWaitMs / 1000}s`,
    };
}

// ============================================================================
// Utility
// ============================================================================

/** Get remaining Creatify API credits. */
export async function getRemainingCredits(): Promise<number> {
    const data = await creatifyFetch<{ remaining_credits: number }>(
        '/workspace/remaining_credits',
    );
    return data.remaining_credits ?? 0;
}

/** List available voices for narration. */
export async function getVoices(language = 'en') {
    return creatifyFetch(`/voices?language=${encodeURIComponent(language)}`);
}

/** List available avatars. */
export async function getAvatars() {
    return creatifyFetch('/personas');
}

// ============================================================================
// High-Level: Generate video ad from URL (end-to-end)
// ============================================================================

export interface GenerateVideoAdParams {
    /** Product URL to generate video from */
    url: string;
    /** Video aspect ratio. Default: "16:9" for YouTube ads */
    aspectRatio?: AspectRatio;
    /** Custom script for the video */
    script?: string;
    /** Voice ID for narration */
    voiceId?: string;
    /** Avatar ID for presenter */
    avatarId?: string;
    /** Wait for video to finish generating. Default: true */
    waitForCompletion?: boolean;
}

/**
 * Generate a video ad from a URL. Full pipeline: URL → link → video → poll.
 *
 * Credit cost: 1 (link) + 5 per 30s (video) = ~6 credits for a 30s video.
 */
export async function generateVideoAd(
    params: GenerateVideoAdParams,
): Promise<VideoResult> {
    // Step 1: Create link from URL
    const link = await createLink(params.url);
    if (!link.id) {
        return { id: '', status: 'failed', error: 'Failed to create link from URL' };
    }

    // Step 2: Generate video
    const video = await createVideo({
        linkId: link.id,
        aspectRatio: params.aspectRatio ?? '16:9',
        script: params.script,
        voiceId: params.voiceId,
        avatarId: params.avatarId,
    });

    if (!video.id) {
        return { id: '', status: 'failed', error: 'Failed to create video' };
    }

    // Step 3: Wait for completion if requested
    if (params.waitForCompletion !== false) {
        return waitForVideo(video.id);
    }

    return video;
}

// ============================================================================
// CodeTether Pre-configured Scripts
// ============================================================================

export const CODETETHER_SCRIPTS = {
    problem_focused: `Stop copy-pasting from ChatGPT into spreadsheets.
CodeTether delivers real files automatically.
Trigger a task, walk away, get CSV, PDF, or code delivered by email.
Works with Zapier, n8n, Make.
Powered by MIT research.
Start free at CodeTether.io`,

    result_focused: `Get a 500-lead scoring spreadsheet delivered to your inbox.
Automatically.
CodeTether runs AI tasks in the background for 5 to 60 minutes.
Then delivers real files: CSV, PDF, code, reports.
No babysitting. No copy-pasting.
Works with Zapier, n8n, Make.
Start free at CodeTether.io`,

    comparison: `ChatGPT is a chat.
CodeTether is a worker.
ChatGPT gives you text. You copy, paste, format.
CodeTether delivers real files. CSV. PDF. Code. Reports.
Trigger once via Zapier. Walk away.
Get deliverables by email.
Powered by MIT research.
Start free at CodeTether.io`,
} as const;

export type ScriptStyle = keyof typeof CODETETHER_SCRIPTS;

/** Generate a pre-configured CodeTether promotional video ad. */
export async function generateCodetetherVideoAd(
    scriptStyle: ScriptStyle = 'problem_focused',
    aspectRatio: AspectRatio = '16:9',
): Promise<VideoResult> {
    return generateVideoAd({
        url: 'https://codetether.io',
        aspectRatio,
        script: CODETETHER_SCRIPTS[scriptStyle],
    });
}
