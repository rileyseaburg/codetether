/**
 * Facebook/Meta Video Ad Pipeline
 *
 * End-to-end: Creatify video → Facebook Ad Account upload → Campaign creation.
 *
 * Facebook video ads require:
 *   Campaign (objective: OUTCOME_AWARENESS or VIDEO_VIEWS)
 *   → Ad Set (optimization_goal: THRUPLAY, targeting)
 *   → Ad Creative (video_data with video_id + page_id)
 *   → Ad (links creative to ad set)
 *
 * @module lib/facebook/videoAds
 */

import {
    createCampaign,
    createAdSet,
    createVideoAdCreative,
    createAd,
    uploadVideoAsset,
    getVideoStatus,
    getCampaignInsights,
    listCampaigns,
} from './client';

// ============================================================================
// Full Pipeline
// ============================================================================

export interface LaunchFacebookVideoAdParams {
    /** Creatify video URL to upload to Facebook */
    videoUrl: string;
    /** Campaign name */
    campaignName?: string;
    /** Daily budget in dollars */
    dailyBudgetDollars?: number;
    /** Landing page URL */
    landingUrl?: string;
    /** Ad message/copy */
    message?: string;
    /** Ad headline */
    headline?: string;
    /** CTA button type (LEARN_MORE, SIGN_UP, etc.) */
    ctaType?: string;
    /** Thumbnail URL for the video */
    thumbnailUrl?: string;
    /** Targeting overrides */
    targeting?: Record<string, unknown>;
    /** Facebook Page ID override */
    pageId?: string;
    /** Ad account ID override */
    accountId?: string;
}

export interface LaunchFacebookVideoAdResult {
    campaignId: string;
    adSetId: string;
    creativeId: string;
    adId: string;
    facebookVideoId: string;
    status: 'PAUSED';
}

/**
 * Full pipeline: Upload video → Create campaign → Ad set → Creative → Ad.
 *
 * All entities are created as PAUSED for review before spending.
 */
export async function launchFacebookVideoAd(
    params: LaunchFacebookVideoAdParams,
): Promise<LaunchFacebookVideoAdResult> {
    const campaignName =
        params.campaignName ??
        `CodeTether Video ${new Date().toISOString().split('T')[0]}`;
    const budgetCents = (params.dailyBudgetDollars ?? 25) * 100;
    const landingUrl = params.landingUrl ?? 'https://codetether.run';

    // 1. Upload video to Facebook
    const video = await uploadVideoAsset({
        videoUrl: params.videoUrl,
        title: campaignName,
        description: 'AI-generated video ad for CodeTether',
        accountId: params.accountId,
    });

    // 2. Create campaign
    const campaign = await createCampaign({
        name: campaignName,
        objective: 'OUTCOME_AWARENESS',
        status: 'PAUSED',
        dailyBudgetCents: budgetCents,
        accountId: params.accountId,
    });

    // 3. Create ad set with targeting
    const adSet = await createAdSet({
        campaignId: campaign.id,
        name: `${campaignName} - Video Viewers`,
        dailyBudgetCents: budgetCents,
        optimizationGoal: 'THRUPLAY',
        billingEvent: 'IMPRESSIONS',
        targeting: params.targeting ?? {
            geo_locations: { countries: ['US'] },
            age_min: 25,
            age_max: 55,
            // Developer / tech audience interests
            flexible_spec: [
                {
                    interests: [
                        { id: '6003139266461', name: 'Software development' },
                        { id: '6003397425735', name: 'Artificial intelligence' },
                        { id: '6003017845546', name: 'GitHub' },
                    ],
                },
            ],
        },
        status: 'PAUSED',
        accountId: params.accountId,
    });

    // 4. Create video ad creative
    const creative = await createVideoAdCreative({
        name: `${campaignName} Creative`,
        videoId: video.id,
        pageId: params.pageId,
        message:
            params.message ??
            'Stop babysitting ChatGPT. CodeTether runs AI tasks in the background and delivers real files — CSV, PDF, code. Trigger once, walk away.',
        title: params.headline ?? 'AI Agents That Actually Deliver',
        callToAction: {
            type: params.ctaType ?? 'LEARN_MORE',
            value: { link: landingUrl },
        },
        thumbnailUrl: params.thumbnailUrl,
        accountId: params.accountId,
    });

    // 5. Create ad
    const ad = await createAd({
        adSetId: adSet.id,
        creativeId: creative.id,
        name: `${campaignName} Ad`,
        status: 'PAUSED',
        accountId: params.accountId,
    });

    return {
        campaignId: campaign.id,
        adSetId: adSet.id,
        creativeId: creative.id,
        adId: ad.id,
        facebookVideoId: video.id,
        status: 'PAUSED',
    };
}

// ============================================================================
// Video Status Check
// ============================================================================

/**
 * Check if a Facebook video has finished processing.
 *
 * Facebook may take 1–5 minutes to process uploaded videos.
 */
export async function checkFacebookVideoStatus(videoId: string) {
    return getVideoStatus(videoId);
}

// ============================================================================
// Reporting
// ============================================================================

/**
 * Get performance report for Facebook video campaigns.
 */
export async function getFacebookVideoReport(params: {
    days?: number;
    campaignId?: string;
    accountId?: string;
}) {
    if (params.campaignId) {
        return getCampaignInsights(params.campaignId, {
            datePreset: `last_${params.days ?? 30}_d`,
        });
    }

    // List all campaigns and get insights for video ones
    const campaigns = await listCampaigns(params.accountId);
    const videoCampaigns = campaigns.filter(
        (c) =>
            c.objective === 'OUTCOME_AWARENESS' ||
            c.objective === 'VIDEO_VIEWS',
    );

    const reports = await Promise.all(
        videoCampaigns.slice(0, 10).map(async (c) => {
            const insights = await getCampaignInsights(c.id, {
                datePreset: `last_${params.days ?? 30}_d`,
            });
            return { campaign: c, insights };
        }),
    );

    return reports;
}
