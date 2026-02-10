/**
 * CodeTether Google Ads Video Ad Service
 *
 * YouTube video asset uploads, VIDEO campaign creation,
 * in-stream (skippable) and bumper (6s non-skippable) ad formats.
 *
 * Designed to accept Creatify-generated videos that have been
 * uploaded to YouTube, then run them as Google Ads video campaigns.
 *
 * @module lib/google/videoAds
 */

import { getCustomer, enums, dollarsToMicros } from './client';

// ============================================================================
// YouTube Video Asset
// ============================================================================

/**
 * Register a YouTube video as a Google Ads asset.
 * The video must already be uploaded to YouTube.
 */
export async function uploadYouTubeAsset(params: {
    youtubeVideoId: string;
    assetName?: string;
    customerId?: string;
}) {
    const customer = getCustomer(params.customerId);
    const cid = params.customerId ?? process.env.GOOGLE_ADS_CUSTOMER_ID!;

    const response = await customer.assets.create([
        {
            type: enums.AssetType.YOUTUBE_VIDEO,
            name: params.assetName ?? `YouTube Video ${params.youtubeVideoId}`,
            youtube_video_asset: {
                youtube_video_id: params.youtubeVideoId,
            },
        },
    ]);

    const resourceName = response.results[0].resource_name;
    const assetId = resourceName.split('/').pop() ?? '';

    return { assetId, resourceName };
}

/**
 * Get details about an asset (video or image)
 */
export async function getAssetDetails(assetId: string, customerId?: string) {
    const customer = getCustomer(customerId);

    const [asset] = await customer.query(`
        SELECT
            asset.id,
            asset.name,
            asset.type,
            asset.youtube_video_asset.youtube_video_id,
            asset.youtube_video_asset.youtube_video_title
        FROM asset
        WHERE asset.id = ${assetId}
    `);

    return asset;
}

// ============================================================================
// Video Campaign
// ============================================================================

/**
 * Create a VIDEO campaign optimized for YouTube ads.
 *
 * Supports bidding strategies appropriate for video:
 * - MAXIMIZE_CONVERSIONS (recommended for direct-response)
 * - TARGET_CPM (brand awareness)
 * - TARGET_CPA (conversion-focused with target cost)
 */
export async function createVideoCampaign(params: {
    name: string;
    dailyBudgetMicros: number;
    biddingStrategy?: 'MAXIMIZE_CONVERSIONS' | 'TARGET_CPM' | 'TARGET_CPA';
    targetCpaMicros?: number;
    customerId?: string;
}) {
    const customer = getCustomer(params.customerId);

    // Create budget
    const budgets = await customer.campaignBudgets.create([
        {
            name: `${params.name} Budget`,
            amount_micros: params.dailyBudgetMicros,
            delivery_method: enums.BudgetDeliveryMethod.STANDARD,
        },
    ]);

    const budgetResourceName = budgets.results[0].resource_name;

    // Build campaign config for VIDEO channel
    const campaignConfig: Record<string, unknown> = {
        name: params.name,
        campaign_budget: budgetResourceName,
        advertising_channel_type: enums.AdvertisingChannelType.VIDEO,
        status: enums.CampaignStatus.PAUSED, // Start paused for review
    };

    switch (params.biddingStrategy ?? 'MAXIMIZE_CONVERSIONS') {
        case 'MAXIMIZE_CONVERSIONS':
            campaignConfig.maximize_conversions = {};
            break;
        case 'TARGET_CPM':
            campaignConfig.target_cpm = {};
            break;
        case 'TARGET_CPA':
            campaignConfig.target_cpa = {
                target_cpa_micros: params.targetCpaMicros ?? 10_000_000, // $10 default
            };
            break;
    }

    const campaigns = await customer.campaigns.create([campaignConfig]);

    return {
        campaignResourceName: campaigns.results[0].resource_name,
        budgetResourceName,
    };
}

// ============================================================================
// Video Ad Groups
// ============================================================================

/**
 * Create a video ad group (TrueView in-stream or bumper)
 */
export async function createVideoAdGroup(params: {
    campaignId: string;
    name: string;
    cpmBidMicros?: number;
    type?: 'IN_STREAM' | 'BUMPER';
    customerId?: string;
}) {
    const customer = getCustomer(params.customerId);
    const cid = params.customerId ?? process.env.GOOGLE_ADS_CUSTOMER_ID!;

    const adGroupType =
        params.type === 'BUMPER'
            ? enums.AdGroupType.VIDEO_BUMPER
            : enums.AdGroupType.VIDEO_TRUE_VIEW_IN_STREAM;

    return customer.adGroups.create([
        {
            campaign: `customers/${cid}/campaigns/${params.campaignId}`,
            name: params.name,
            status: enums.AdGroupStatus.ENABLED,
            type: adGroupType,
            cpm_bid_micros: params.cpmBidMicros,
        },
    ]);
}

// ============================================================================
// Video Ads
// ============================================================================

/**
 * Create a skippable in-stream video ad (TrueView).
 *
 * The YouTube video must already be registered as a Google Ads asset.
 * If not, pass youtubeVideoId and it will be auto-registered.
 */
export async function createInStreamVideoAd(params: {
    adGroupId: string;
    youtubeVideoId: string;
    finalUrl: string;
    displayUrl: string;
    headline?: string;
    callToAction?: string;
    customerId?: string;
}) {
    const customer = getCustomer(params.customerId);
    const cid = params.customerId ?? process.env.GOOGLE_ADS_CUSTOMER_ID!;

    // Register YouTube video as asset
    const { assetId } = await uploadYouTubeAsset({
        youtubeVideoId: params.youtubeVideoId,
        customerId: params.customerId,
    });

    const inStreamConfig: Record<string, unknown> = {
        action_button_label: params.callToAction ?? 'Learn More',
    };
    if (params.headline) {
        inStreamConfig.action_headline = params.headline;
    }

    return customer.adGroupAds.create([
        {
            ad_group: `customers/${cid}/adGroups/${params.adGroupId}`,
            status: enums.AdGroupAdStatus.ENABLED,
            ad: {
                final_urls: [params.finalUrl],
                display_url: params.displayUrl,
                video_ad: {
                    video: {
                        asset: `customers/${cid}/assets/${assetId}`,
                    },
                    in_stream: inStreamConfig,
                },
            },
        },
    ]);
}

/**
 * Create a non-skippable 6-second bumper ad.
 */
export async function createBumperVideoAd(params: {
    adGroupId: string;
    youtubeVideoId: string;
    finalUrl: string;
    displayUrl: string;
    customerId?: string;
}) {
    const customer = getCustomer(params.customerId);
    const cid = params.customerId ?? process.env.GOOGLE_ADS_CUSTOMER_ID!;

    // Register YouTube video as asset
    const { assetId } = await uploadYouTubeAsset({
        youtubeVideoId: params.youtubeVideoId,
        customerId: params.customerId,
    });

    return customer.adGroupAds.create([
        {
            ad_group: `customers/${cid}/adGroups/${params.adGroupId}`,
            status: enums.AdGroupAdStatus.ENABLED,
            ad: {
                final_urls: [params.finalUrl],
                display_url: params.displayUrl,
                video_ad: {
                    video: {
                        asset: `customers/${cid}/assets/${assetId}`,
                    },
                    bumper: {},
                },
            },
        },
    ]);
}

/**
 * List video ads (in-stream + bumper) with metrics
 */
export async function listVideoAds(params: {
    adGroupId?: string;
    campaignId?: string;
    customerId?: string;
}) {
    const customer = getCustomer(params.customerId);
    const cid = params.customerId ?? process.env.GOOGLE_ADS_CUSTOMER_ID!;

    let whereClause = `ad_group_ad.ad.type IN ('VIDEO_TRUE_VIEW_IN_STREAM', 'VIDEO_BUMPER', 'VIDEO_RESPONSIVE')`;

    if (params.adGroupId) {
        whereClause += ` AND ad_group_ad.ad_group = 'customers/${cid}/adGroups/${params.adGroupId}'`;
    }
    if (params.campaignId) {
        whereClause += ` AND campaign.id = ${params.campaignId}`;
    }

    return customer.query(`
        SELECT
            ad_group_ad.ad.id,
            ad_group_ad.ad.name,
            ad_group_ad.status,
            ad_group_ad.ad.type,
            ad_group_ad.ad_group,
            ad_group_ad.ad.final_urls,
            ad_group_ad.ad.display_url,
            ad_group_ad.ad.video_ad.video.asset,
            ad_group_ad.ad.video_ad.in_stream.action_button_label,
            ad_group_ad.ad.video_ad.in_stream.action_headline,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.video_views,
            metrics.video_view_rate
        FROM ad_group_ad
        WHERE ${whereClause}
        ORDER BY ad_group_ad.ad.id
    `);
}

/**
 * Get video campaign performance report
 */
export async function getVideoReport(params: {
    startDate: string;
    endDate: string;
    customerId?: string;
}) {
    const customer = getCustomer(params.customerId);

    const rows = await customer.query(`
        SELECT
            campaign.id,
            campaign.name,
            campaign.status,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.video_views,
            metrics.video_view_rate,
            metrics.video_quartile_p25_rate,
            metrics.video_quartile_p50_rate,
            metrics.video_quartile_p75_rate,
            metrics.video_quartile_p100_rate,
            metrics.average_cpv,
            segments.date
        FROM campaign
        WHERE campaign.advertising_channel_type = 'VIDEO'
            AND segments.date BETWEEN '${params.startDate}' AND '${params.endDate}'
            AND campaign.status != 'REMOVED'
        ORDER BY metrics.cost_micros DESC
    `);

    return rows.map((row: any) => ({
        campaignId: String(row.campaign.id),
        campaignName: row.campaign.name,
        status: row.campaign.status,
        impressions: Number(row.metrics.impressions) || 0,
        clicks: Number(row.metrics.clicks) || 0,
        costMicros: Number(row.metrics.cost_micros) || 0,
        conversions: Number(row.metrics.conversions) || 0,
        videoViews: Number(row.metrics.video_views) || 0,
        viewRate: Number(row.metrics.video_view_rate) || 0,
        quartile25: Number(row.metrics.video_quartile_p25_rate) || 0,
        quartile50: Number(row.metrics.video_quartile_p50_rate) || 0,
        quartile75: Number(row.metrics.video_quartile_p75_rate) || 0,
        quartile100: Number(row.metrics.video_quartile_p100_rate) || 0,
        avgCpv: Number(row.metrics.average_cpv) || 0,
        date: row.segments?.date,
    }));
}

// ============================================================================
// Audience Targeting
// ============================================================================

/**
 * Attach a remarketing audience to a video ad group
 */
export async function attachAudienceToAdGroup(params: {
    adGroupId: string;
    userListId: string;
    bidModifier?: number;
    customerId?: string;
}) {
    const customer = getCustomer(params.customerId);
    const cid = params.customerId ?? process.env.GOOGLE_ADS_CUSTOMER_ID!;

    return customer.adGroupCriteria.create([
        {
            ad_group: `customers/${cid}/adGroups/${params.adGroupId}`,
            user_list: {
                user_list: `customers/${cid}/userLists/${params.userListId}`,
            },
            bid_modifier: params.bidModifier ?? 1.0,
        },
    ]);
}

// ============================================================================
// Full Pipeline: Creatify Video → YouTube → Google Ads
// ============================================================================

/**
 * Complete pipeline to run a Creatify-generated video as a Google Ad.
 *
 * Assumes the video has already been uploaded to YouTube.
 * Creates: campaign → ad group → in-stream video ad
 *
 * @returns Campaign + ad group + ad resource names
 */
export async function launchVideoAdFromYouTube(params: {
    youtubeVideoId: string;
    campaignName: string;
    dailyBudgetDollars: number;
    finalUrl?: string;
    displayUrl?: string;
    headline?: string;
    callToAction?: string;
    adType?: 'IN_STREAM' | 'BUMPER';
    customerId?: string;
}) {
    const finalUrl = params.finalUrl ?? 'https://codetether.run';
    const displayUrl = params.displayUrl ?? 'codetether.run';

    // 1. Create VIDEO campaign
    const campaign = await createVideoCampaign({
        name: params.campaignName,
        dailyBudgetMicros: dollarsToMicros(params.dailyBudgetDollars),
        biddingStrategy: 'MAXIMIZE_CONVERSIONS',
        customerId: params.customerId,
    });

    // Extract campaign ID from resource name
    const campaignId = campaign.campaignResourceName.split('/').pop()!;

    // 2. Create video ad group
    const adGroup = await createVideoAdGroup({
        campaignId,
        name: `${params.campaignName} - Video`,
        type: params.adType ?? 'IN_STREAM',
        customerId: params.customerId,
    });

    const adGroupId = adGroup.results[0].resource_name.split('/').pop()!;

    // 3. Create video ad
    let ad;
    if (params.adType === 'BUMPER') {
        ad = await createBumperVideoAd({
            adGroupId,
            youtubeVideoId: params.youtubeVideoId,
            finalUrl,
            displayUrl,
            customerId: params.customerId,
        });
    } else {
        ad = await createInStreamVideoAd({
            adGroupId,
            youtubeVideoId: params.youtubeVideoId,
            finalUrl,
            displayUrl,
            headline: params.headline ?? 'AI Agents That Actually Deliver',
            callToAction: params.callToAction ?? 'Start Free',
            customerId: params.customerId,
        });
    }

    return {
        campaignResourceName: campaign.campaignResourceName,
        campaignId,
        budgetResourceName: campaign.budgetResourceName,
        adGroupId,
        adResourceName: ad.results[0].resource_name,
        status: 'PAUSED', // Campaign starts paused for review
    };
}
