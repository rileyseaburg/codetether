/**
 * CodeTether Google Ads API Client
 *
 * Wraps the google-ads-api package for campaign management,
 * ad group operations, and responsive search ads.
 *
 * Uses Standard Access (full campaign management).
 * All monetary values use micros (1 dollar = 1,000,000 micros).
 *
 * Required env vars:
 *   GOOGLE_ADS_CLIENT_ID
 *   GOOGLE_ADS_CLIENT_SECRET
 *   GOOGLE_ADS_DEVELOPER_TOKEN
 *   GOOGLE_ADS_REFRESH_TOKEN
 *   GOOGLE_ADS_CUSTOMER_ID
 *
 * @module lib/google/client
 */

import { GoogleAdsApi, enums } from 'google-ads-api';

export { enums };

// ============================================================================
// Singleton client
// ============================================================================

let _client: GoogleAdsApi | null = null;

function getClient(): GoogleAdsApi {
    if (_client) return _client;

    const clientId = process.env.GOOGLE_ADS_CLIENT_ID;
    const clientSecret = process.env.GOOGLE_ADS_CLIENT_SECRET;
    const developerToken = process.env.GOOGLE_ADS_DEVELOPER_TOKEN;

    if (!clientId || !clientSecret || !developerToken) {
        throw new Error(
            'Missing Google Ads credentials. Set GOOGLE_ADS_CLIENT_ID, GOOGLE_ADS_CLIENT_SECRET, GOOGLE_ADS_DEVELOPER_TOKEN'
        );
    }

    _client = new GoogleAdsApi({
        client_id: clientId,
        client_secret: clientSecret,
        developer_token: developerToken,
    });

    return _client;
}

/**
 * Get a Google Ads customer instance for API operations
 */
export function getCustomer(customerId?: string, refreshToken?: string) {
    const client = getClient();
    const cid = customerId ?? process.env.GOOGLE_ADS_CUSTOMER_ID;
    const token = refreshToken ?? process.env.GOOGLE_ADS_REFRESH_TOKEN;

    if (!cid) throw new Error('No Google Ads customer ID provided');
    if (!token) throw new Error('No Google Ads refresh token provided');

    return client.Customer({
        customer_id: cid,
        refresh_token: token,
    });
}

// ============================================================================
// Campaign operations
// ============================================================================

/**
 * List all campaigns for a customer
 */
export async function listCampaigns(customerId?: string) {
    const customer = getCustomer(customerId);

    const campaigns = await customer.query(`
        SELECT
            campaign.id,
            campaign.name,
            campaign.status,
            campaign.advertising_channel_type,
            campaign.bidding_strategy_type,
            campaign.campaign_budget,
            campaign_budget.amount_micros,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.conversions_value
        FROM campaign
        WHERE campaign.status != 'REMOVED'
        ORDER BY campaign.id
    `);

    return campaigns;
}

/**
 * Get a single campaign with budget info
 */
export async function getCampaign(campaignId: string, customerId?: string) {
    const customer = getCustomer(customerId);

    const [campaign] = await customer.query(`
        SELECT
            campaign.id,
            campaign.name,
            campaign.status,
            campaign.advertising_channel_type,
            campaign.bidding_strategy_type,
            campaign.campaign_budget,
            campaign_budget.amount_micros,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.conversions_value
        FROM campaign
        WHERE campaign.id = ${campaignId}
    `);

    return campaign;
}

/**
 * Create a search campaign with budget
 */
export async function createCampaign(params: {
    name: string;
    dailyBudgetMicros: number;
    channelType?: keyof typeof enums.AdvertisingChannelType;
    biddingStrategy?: 'MAXIMIZE_CONVERSIONS' | 'MAXIMIZE_CLICKS' | 'TARGET_CPA' | 'MANUAL_CPC';
    targetCpaMicros?: number;
    customerId?: string;
}) {
    const customer = getCustomer(params.customerId);
    const cid = params.customerId ?? process.env.GOOGLE_ADS_CUSTOMER_ID!;

    // Create campaign budget first
    const budgets = await customer.campaignBudgets.create([
        {
            name: `${params.name} Budget`,
            amount_micros: params.dailyBudgetMicros,
            delivery_method: enums.BudgetDeliveryMethod.STANDARD,
        },
    ]);

    const budgetResourceName = budgets.results[0].resource_name;

    // Build campaign config
    const campaignConfig: Record<string, unknown> = {
        name: params.name,
        campaign_budget: budgetResourceName,
        advertising_channel_type:
            enums.AdvertisingChannelType[params.channelType ?? 'SEARCH'],
        status: enums.CampaignStatus.PAUSED, // Start paused for review
        network_settings: {
            target_google_search: true,
            target_search_network: true,
            target_content_network: false,
        },
    };

    // Set bidding strategy
    switch (params.biddingStrategy ?? 'MAXIMIZE_CONVERSIONS') {
        case 'MAXIMIZE_CONVERSIONS':
            campaignConfig.maximize_conversions = {};
            break;
        case 'MAXIMIZE_CLICKS':
            campaignConfig.maximize_clicks = {};
            break;
        case 'TARGET_CPA':
            campaignConfig.target_cpa = {
                target_cpa_micros: params.targetCpaMicros ?? 5_000_000, // $5 default
            };
            break;
        case 'MANUAL_CPC':
            campaignConfig.manual_cpc = { enhanced_cpc_enabled: true };
            break;
    }

    const campaigns = await customer.campaigns.create([campaignConfig]);

    return {
        campaignResourceName: campaigns.results[0].resource_name,
        budgetResourceName,
    };
}

/**
 * Update campaign status (ENABLED, PAUSED, REMOVED)
 */
export async function updateCampaignStatus(
    campaignId: string,
    status: 'ENABLED' | 'PAUSED' | 'REMOVED',
    customerId?: string
) {
    const customer = getCustomer(customerId);
    const cid = customerId ?? process.env.GOOGLE_ADS_CUSTOMER_ID!;

    await customer.campaigns.update([
        {
            resource_name: `customers/${cid}/campaigns/${campaignId}`,
            status: enums.CampaignStatus[status],
        },
    ]);
}

/**
 * Update campaign daily budget
 */
export async function updateCampaignBudget(
    campaignId: string,
    newBudgetMicros: number,
    customerId?: string
) {
    const customer = getCustomer(customerId);
    const cid = customerId ?? process.env.GOOGLE_ADS_CUSTOMER_ID!;

    // First get the budget resource name
    const [campaign] = await customer.query(`
        SELECT campaign.campaign_budget
        FROM campaign
        WHERE campaign.id = ${campaignId}
    `);

    if (!campaign?.campaign?.campaign_budget) {
        throw new Error(`Campaign ${campaignId} not found or has no budget`);
    }

    await customer.campaignBudgets.update([
        {
            resource_name: campaign.campaign.campaign_budget,
            amount_micros: newBudgetMicros,
        },
    ]);
}

// ============================================================================
// Ad Group operations
// ============================================================================

/**
 * List ad groups for a campaign
 */
export async function listAdGroups(campaignId: string, customerId?: string) {
    const customer = getCustomer(customerId);
    const cid = customerId ?? process.env.GOOGLE_ADS_CUSTOMER_ID!;

    return customer.query(`
        SELECT
            ad_group.id,
            ad_group.name,
            ad_group.status,
            ad_group.type,
            ad_group.cpc_bid_micros,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions
        FROM ad_group
        WHERE ad_group.campaign = 'customers/${cid}/campaigns/${campaignId}'
        ORDER BY ad_group.id
    `);
}

/**
 * Create an ad group in a campaign
 */
export async function createAdGroup(params: {
    campaignId: string;
    name: string;
    cpcBidMicros?: number;
    type?: keyof typeof enums.AdGroupType;
    customerId?: string;
}) {
    const customer = getCustomer(params.customerId);
    const cid = params.customerId ?? process.env.GOOGLE_ADS_CUSTOMER_ID!;

    return customer.adGroups.create([
        {
            campaign: `customers/${cid}/campaigns/${params.campaignId}`,
            name: params.name,
            status: enums.AdGroupStatus.ENABLED,
            type: enums.AdGroupType[params.type ?? 'SEARCH_STANDARD'],
            cpc_bid_micros: params.cpcBidMicros,
        },
    ]);
}

/**
 * Update ad group CPC bid
 */
export async function updateAdGroupBid(
    adGroupId: string,
    cpcBidMicros: number,
    customerId?: string
) {
    const customer = getCustomer(customerId);
    const cid = customerId ?? process.env.GOOGLE_ADS_CUSTOMER_ID!;

    await customer.adGroups.update([
        {
            resource_name: `customers/${cid}/adGroups/${adGroupId}`,
            cpc_bid_micros: cpcBidMicros,
        },
    ]);
}

// ============================================================================
// Responsive Search Ad operations
// ============================================================================

/**
 * Create a responsive search ad in an ad group
 */
export async function createResponsiveSearchAd(params: {
    adGroupId: string;
    headlines: string[];
    descriptions: string[];
    finalUrls: string[];
    path1?: string;
    path2?: string;
    customerId?: string;
}) {
    const customer = getCustomer(params.customerId);
    const cid = params.customerId ?? process.env.GOOGLE_ADS_CUSTOMER_ID!;

    // Validate: 3-15 headlines (<=30 chars each), 2-4 descriptions (<=90 chars each)
    if (params.headlines.length < 3 || params.headlines.length > 15) {
        throw new Error(`Headlines must have 3-15 entries, got ${params.headlines.length}`);
    }
    if (params.descriptions.length < 2 || params.descriptions.length > 4) {
        throw new Error(`Descriptions must have 2-4 entries, got ${params.descriptions.length}`);
    }

    const invalidHeadlines = params.headlines.filter(h => h.length > 30);
    if (invalidHeadlines.length > 0) {
        throw new Error(`Headlines exceeding 30 chars: ${invalidHeadlines.join(', ')}`);
    }

    const invalidDescriptions = params.descriptions.filter(d => d.length > 90);
    if (invalidDescriptions.length > 0) {
        throw new Error(`Descriptions exceeding 90 chars: ${invalidDescriptions.join(', ')}`);
    }

    return customer.adGroupAds.create([
        {
            ad_group: `customers/${cid}/adGroups/${params.adGroupId}`,
            status: enums.AdGroupAdStatus.ENABLED,
            ad: {
                final_urls: params.finalUrls,
                responsive_search_ad: {
                    headlines: params.headlines.map(text => ({ text })),
                    descriptions: params.descriptions.map(text => ({ text })),
                    path1: params.path1,
                    path2: params.path2,
                },
            },
        },
    ]);
}

/**
 * List ads in an ad group
 */
export async function listAds(adGroupId: string, customerId?: string) {
    const customer = getCustomer(customerId);
    const cid = customerId ?? process.env.GOOGLE_ADS_CUSTOMER_ID!;

    return customer.query(`
        SELECT
            ad_group_ad.ad.id,
            ad_group_ad.ad.name,
            ad_group_ad.status,
            ad_group_ad.ad.type,
            ad_group_ad.ad.final_urls,
            ad_group_ad.ad.responsive_search_ad.headlines,
            ad_group_ad.ad.responsive_search_ad.descriptions,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions
        FROM ad_group_ad
        WHERE ad_group_ad.ad_group = 'customers/${cid}/adGroups/${adGroupId}'
        ORDER BY ad_group_ad.ad.id
    `);
}

// ============================================================================
// Keyword operations
// ============================================================================

/**
 * Add keywords to an ad group
 */
export async function addKeywords(params: {
    adGroupId: string;
    keywords: Array<{
        text: string;
        matchType: 'EXACT' | 'PHRASE' | 'BROAD';
    }>;
    customerId?: string;
}) {
    const customer = getCustomer(params.customerId);
    const cid = params.customerId ?? process.env.GOOGLE_ADS_CUSTOMER_ID!;

    return customer.adGroupCriteria.create(
        params.keywords.map(kw => ({
            ad_group: `customers/${cid}/adGroups/${params.adGroupId}`,
            status: enums.AdGroupCriterionStatus.ENABLED,
            keyword: {
                text: kw.text,
                match_type: enums.KeywordMatchType[kw.matchType],
            },
        }))
    );
}

/**
 * Add negative keywords to a campaign
 */
export async function addNegativeKeywords(params: {
    campaignId: string;
    keywords: string[];
    customerId?: string;
}) {
    const customer = getCustomer(params.customerId);
    const cid = params.customerId ?? process.env.GOOGLE_ADS_CUSTOMER_ID!;

    return customer.campaignCriteria.create(
        params.keywords.map(kw => ({
            campaign: `customers/${cid}/campaigns/${params.campaignId}`,
            negative: true,
            keyword: {
                text: kw,
                match_type: enums.KeywordMatchType.PHRASE,
            },
        }))
    );
}

// ============================================================================
// Helpers
// ============================================================================

/**
 * Convert dollars to micros
 */
export function dollarsToMicros(dollars: number): number {
    return Math.round(dollars * 1_000_000);
}

/**
 * Convert micros to dollars
 */
export function microsToDollars(micros: number): number {
    return micros / 1_000_000;
}

/**
 * Convert cents to micros (for Thompson Sampling integration)
 */
export function centsToMicros(cents: number): number {
    return Math.round(cents * 10_000);
}

/**
 * Convert micros to cents (for Thompson Sampling integration)
 */
export function microsToCents(micros: number): number {
    return Math.round(micros / 10_000);
}
