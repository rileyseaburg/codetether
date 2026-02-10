/**
 * Facebook/Meta Marketing API Client
 *
 * Core client for Facebook Ads operations via the Graph API.
 * Handles authentication, rate limiting, and basic CRUD for
 * campaigns, ad sets, ads, and creatives.
 *
 * Required env vars:
 *   FACEBOOK_ACCESS_TOKEN   - Long-lived user or system user token
 *   FACEBOOK_AD_ACCOUNT_ID  - Ad account ID (with or without act_ prefix)
 *   FACEBOOK_APP_SECRET     - (optional) For appsecret_proof
 *   FACEBOOK_PAGE_ID        - Facebook Page ID for ad creatives
 *
 * @module lib/facebook/client
 */

import crypto from 'crypto';

const GRAPH_API_VERSION = 'v24.0';
const BASE_URL = `https://graph.facebook.com/${GRAPH_API_VERSION}`;

// ============================================================================
// Auth & Config
// ============================================================================

function getAccessToken(): string {
    const token = process.env.FACEBOOK_ACCESS_TOKEN;
    if (!token) throw new Error('FACEBOOK_ACCESS_TOKEN not set');
    return token;
}

function getAdAccountId(): string {
    const id = process.env.FACEBOOK_AD_ACCOUNT_ID;
    if (!id) throw new Error('FACEBOOK_AD_ACCOUNT_ID not set');
    return id.startsWith('act_') ? id : `act_${id}`;
}

function getPageId(): string {
    const id = process.env.FACEBOOK_PAGE_ID;
    if (!id) throw new Error('FACEBOOK_PAGE_ID not set');
    return id;
}

/**
 * Generate appsecret_proof if FACEBOOK_APP_SECRET is set.
 * This is required for server-to-server calls when app-level auth is configured.
 */
function getAppSecretProof(token: string): string | undefined {
    const secret = process.env.FACEBOOK_APP_SECRET;
    if (!secret) return undefined;
    return crypto.createHmac('sha256', secret).update(token).digest('hex');
}

// ============================================================================
// HTTP Client with Rate Limit Retry
// ============================================================================

async function fbFetch<T = unknown>(
    endpoint: string,
    options: {
        method?: string;
        body?: Record<string, unknown> | URLSearchParams;
        token?: string;
    } = {},
): Promise<T> {
    const token = options.token ?? getAccessToken();
    const proof = getAppSecretProof(token);

    const url = new URL(`${BASE_URL}${endpoint}`);
    url.searchParams.set('access_token', token);
    if (proof) url.searchParams.set('appsecret_proof', proof);

    const fetchOptions: RequestInit = {
        method: options.method ?? 'GET',
    };

    if (options.body) {
        if (options.body instanceof URLSearchParams) {
            fetchOptions.body = options.body.toString();
            fetchOptions.headers = { 'Content-Type': 'application/x-www-form-urlencoded' };
        } else {
            fetchOptions.body = JSON.stringify(options.body);
            fetchOptions.headers = { 'Content-Type': 'application/json' };
        }
    }

    // Retry up to 3 times for rate limits
    for (let attempt = 0; attempt < 3; attempt++) {
        const res = await fetch(url.toString(), fetchOptions);

        if (res.ok) {
            return res.json() as Promise<T>;
        }

        const errorBody = await res.json().catch(() => ({})) as {
            error?: { message?: string; code?: number; error_subcode?: number };
        };
        const fbErr = errorBody.error ?? {};

        // Rate limit: codes 17, 4, 80004, or HTTP 429
        const isRateLimit =
            fbErr.code === 17 ||
            fbErr.code === 4 ||
            fbErr.code === 80004 ||
            res.status === 429;

        if (isRateLimit && attempt < 2) {
            const delay = Math.pow(2, attempt) * 30_000; // 30s, 60s
            console.warn(`[Facebook API] Rate limited, waiting ${delay / 1000}s...`);
            await new Promise((r) => setTimeout(r, delay));
            continue;
        }

        throw new Error(
            `Facebook API ${res.status}: ${fbErr.message ?? res.statusText} (code: ${fbErr.code}, subcode: ${fbErr.error_subcode})`,
        );
    }

    throw new Error('Facebook API: max retries exceeded');
}

// ============================================================================
// Ad Account
// ============================================================================

export interface FacebookAdAccount {
    id: string;
    account_id: string;
    name: string;
    currency: string;
    account_status: number;
}

export async function getAdAccount(accountId?: string): Promise<FacebookAdAccount> {
    const id = accountId ?? getAdAccountId();
    return fbFetch<FacebookAdAccount>(
        `/${id}?fields=id,account_id,name,currency,account_status`,
    );
}

// ============================================================================
// Campaigns
// ============================================================================

export interface FacebookCampaign {
    id: string;
    name: string;
    status: string;
    objective: string;
    daily_budget?: string;
    lifetime_budget?: string;
}

export async function listCampaigns(accountId?: string): Promise<FacebookCampaign[]> {
    const id = accountId ?? getAdAccountId();
    const res = await fbFetch<{ data: FacebookCampaign[] }>(
        `/${id}/campaigns?fields=id,name,status,objective,daily_budget,lifetime_budget&limit=50`,
    );
    return res.data ?? [];
}

export async function createCampaign(params: {
    name: string;
    objective: string;
    status?: string;
    dailyBudgetCents?: number;
    specialAdCategories?: string[];
    accountId?: string;
}): Promise<{ id: string }> {
    const id = params.accountId ?? getAdAccountId();

    const body = new URLSearchParams();
    body.set('name', params.name);
    body.set('objective', params.objective);
    body.set('status', params.status ?? 'PAUSED');
    body.set(
        'special_ad_categories',
        JSON.stringify(params.specialAdCategories ?? ['NONE']),
    );
    if (params.dailyBudgetCents) {
        body.set('daily_budget', params.dailyBudgetCents.toString());
    }

    return fbFetch<{ id: string }>(`/${id}/campaigns`, {
        method: 'POST',
        body,
    });
}

export async function updateCampaignStatus(
    campaignId: string,
    status: 'ACTIVE' | 'PAUSED' | 'DELETED',
): Promise<{ success: boolean }> {
    const body = new URLSearchParams();
    body.set('status', status);
    return fbFetch<{ success: boolean }>(`/${campaignId}`, {
        method: 'POST',
        body,
    });
}

// ============================================================================
// Ad Sets
// ============================================================================

export interface FacebookAdSet {
    id: string;
    name: string;
    campaign_id: string;
    status: string;
    daily_budget?: string;
    optimization_goal?: string;
    billing_event?: string;
    targeting?: Record<string, unknown>;
}

export async function createAdSet(params: {
    campaignId: string;
    name: string;
    dailyBudgetCents: number;
    optimizationGoal?: string;
    billingEvent?: string;
    targeting?: Record<string, unknown>;
    startTime?: string;
    endTime?: string;
    status?: string;
    accountId?: string;
}): Promise<{ id: string }> {
    const id = params.accountId ?? getAdAccountId();

    const body = new URLSearchParams();
    body.set('campaign_id', params.campaignId);
    body.set('name', params.name);
    body.set('daily_budget', params.dailyBudgetCents.toString());
    body.set('optimization_goal', params.optimizationGoal ?? 'THRUPLAY');
    body.set('billing_event', params.billingEvent ?? 'IMPRESSIONS');
    body.set('bid_strategy', 'LOWEST_COST_WITHOUT_CAP');
    body.set('status', params.status ?? 'PAUSED');
    body.set(
        'targeting',
        JSON.stringify(
            params.targeting ?? {
                geo_locations: { countries: ['US'] },
                age_min: 25,
                age_max: 55,
            },
        ),
    );
    if (params.startTime) body.set('start_time', params.startTime);
    if (params.endTime) body.set('end_time', params.endTime);

    return fbFetch<{ id: string }>(`/${id}/adsets`, {
        method: 'POST',
        body,
    });
}

// ============================================================================
// Ad Creatives
// ============================================================================

/**
 * Create a video ad creative with object_story_spec.
 * The video must already be uploaded to the ad account via uploadVideoAsset().
 */
export async function createVideoAdCreative(params: {
    name: string;
    videoId: string;
    pageId?: string;
    message?: string;
    title?: string;
    linkDescription?: string;
    callToAction?: { type: string; value: { link: string } };
    thumbnailUrl?: string;
    accountId?: string;
}): Promise<{ id: string }> {
    const id = params.accountId ?? getAdAccountId();
    const pageId = params.pageId ?? getPageId();

    const videoData: Record<string, unknown> = {
        video_id: params.videoId,
        message: params.message ?? 'AI agents that actually deliver files.',
        title: params.title ?? 'CodeTether',
    };
    if (params.linkDescription) {
        videoData.link_description = params.linkDescription;
    }
    if (params.thumbnailUrl) {
        videoData.image_url = params.thumbnailUrl;
    }
    if (params.callToAction) {
        videoData.call_to_action = params.callToAction;
    } else {
        videoData.call_to_action = {
            type: 'LEARN_MORE',
            value: { link: 'https://codetether.run' },
        };
    }

    const body = new URLSearchParams();
    body.set('name', params.name);
    body.set(
        'object_story_spec',
        JSON.stringify({
            page_id: pageId,
            video_data: videoData,
        }),
    );

    return fbFetch<{ id: string }>(`/${id}/adcreatives`, {
        method: 'POST',
        body,
    });
}

// ============================================================================
// Ads
// ============================================================================

export async function createAd(params: {
    adSetId: string;
    creativeId: string;
    name: string;
    status?: string;
    accountId?: string;
}): Promise<{ id: string }> {
    const id = params.accountId ?? getAdAccountId();

    const body = new URLSearchParams();
    body.set('name', params.name);
    body.set('adset_id', params.adSetId);
    body.set('creative', JSON.stringify({ creative_id: params.creativeId }));
    body.set('status', params.status ?? 'PAUSED');

    return fbFetch<{ id: string }>(`/${id}/ads`, {
        method: 'POST',
        body,
    });
}

// ============================================================================
// Video Asset Upload
// ============================================================================

/**
 * Upload a video to the ad account by URL.
 * Facebook downloads the video from the URL.
 */
export async function uploadVideoAsset(params: {
    videoUrl: string;
    title?: string;
    description?: string;
    accountId?: string;
}): Promise<{ id: string }> {
    const id = params.accountId ?? getAdAccountId();

    const body: Record<string, unknown> = {
        file_url: params.videoUrl,
    };
    if (params.title) body.title = params.title;
    if (params.description) body.description = params.description;

    return fbFetch<{ id: string }>(`/${id}/advideos`, {
        method: 'POST',
        body,
    });
}

/**
 * Check video processing status.
 */
export async function getVideoStatus(videoId: string): Promise<{
    id: string;
    status: Record<string, unknown>;
    length?: number;
    picture?: string;
}> {
    return fbFetch(`/${videoId}?fields=id,status,length,picture,thumbnails`);
}

// ============================================================================
// Insights / Reporting
// ============================================================================

export async function getCampaignInsights(
    campaignId: string,
    params?: {
        datePreset?: string;
        timeRange?: { since: string; until: string };
        fields?: string[];
    },
): Promise<unknown[]> {
    const fields = (
        params?.fields ?? [
            'impressions',
            'clicks',
            'spend',
            'actions',
            'video_p25_watched_actions',
            'video_p50_watched_actions',
            'video_p75_watched_actions',
            'video_p100_watched_actions',
            'video_thruplay_watched_actions',
            'cost_per_thruplay',
        ]
    ).join(',');

    let qs = `fields=${fields}`;
    if (params?.datePreset) qs += `&date_preset=${params.datePreset}`;
    if (params?.timeRange) {
        qs += `&time_range=${JSON.stringify(params.timeRange)}`;
    }

    const res = await fbFetch<{ data: unknown[] }>(
        `/${campaignId}/insights?${qs}`,
    );
    return res.data ?? [];
}

// ============================================================================
// Exports for convenience
// ============================================================================

export { getAccessToken, getAdAccountId, getPageId, fbFetch };
