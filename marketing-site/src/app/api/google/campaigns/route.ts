/**
 * Google Ads Campaign Management API
 *
 * POST /api/google/campaigns       - List campaigns
 * POST /api/google/campaigns/create - Create campaign
 * POST /api/google/campaigns/status - Update status
 * POST /api/google/campaigns/budget - Update budget
 *
 * All POST to avoid query string parameter leaking in server logs.
 */

import { NextRequest, NextResponse } from 'next/server';
import {
    listCampaigns,
    getCampaign,
    createCampaign,
    updateCampaignStatus,
    updateCampaignBudget,
    listAdGroups,
    createAdGroup,
    updateAdGroupBid,
    createResponsiveSearchAd,
    listAds,
    addKeywords,
    addNegativeKeywords,
    dollarsToMicros,
} from '@/lib/google/client';

function errorResponse(message: string, status = 400) {
    return NextResponse.json({ error: message }, { status });
}

function assertApiKey(request: NextRequest): boolean {
    const key = request.headers.get('x-api-key');
    const expected = process.env.GOOGLE_ADS_INTERNAL_API_KEY;
    if (!expected) return true; // No key configured = development mode
    return key === expected;
}

/**
 * POST: dispatch campaign operations via `action` field
 */
export async function POST(request: NextRequest) {
    if (!assertApiKey(request)) {
        return errorResponse('Unauthorized', 401);
    }

    try {
        const body = await request.json();
        const { action, ...params } = body;

        switch (action) {
            // ---- Campaigns ----
            case 'list_campaigns': {
                const campaigns = await listCampaigns(params.customerId);
                return NextResponse.json({ campaigns });
            }

            case 'get_campaign': {
                if (!params.campaignId) return errorResponse('campaignId required');
                const campaign = await getCampaign(params.campaignId, params.customerId);
                return NextResponse.json({ campaign });
            }

            case 'create_campaign': {
                if (!params.name) return errorResponse('name required');
                if (!params.dailyBudgetDollars && !params.dailyBudgetMicros)
                    return errorResponse('dailyBudgetDollars or dailyBudgetMicros required');

                const result = await createCampaign({
                    name: params.name,
                    dailyBudgetMicros:
                        params.dailyBudgetMicros ?? dollarsToMicros(params.dailyBudgetDollars),
                    channelType: params.channelType,
                    biddingStrategy: params.biddingStrategy,
                    targetCpaMicros: params.targetCpaMicros,
                    customerId: params.customerId,
                });
                return NextResponse.json(result, { status: 201 });
            }

            case 'update_status': {
                if (!params.campaignId || !params.status)
                    return errorResponse('campaignId and status required');
                await updateCampaignStatus(params.campaignId, params.status, params.customerId);
                return NextResponse.json({ ok: true });
            }

            case 'update_budget': {
                if (!params.campaignId) return errorResponse('campaignId required');
                if (!params.dailyBudgetDollars && !params.dailyBudgetMicros)
                    return errorResponse('dailyBudgetDollars or dailyBudgetMicros required');

                await updateCampaignBudget(
                    params.campaignId,
                    params.dailyBudgetMicros ?? dollarsToMicros(params.dailyBudgetDollars),
                    params.customerId
                );
                return NextResponse.json({ ok: true });
            }

            // ---- Ad Groups ----
            case 'list_ad_groups': {
                if (!params.campaignId) return errorResponse('campaignId required');
                const adGroups = await listAdGroups(params.campaignId, params.customerId);
                return NextResponse.json({ adGroups });
            }

            case 'create_ad_group': {
                if (!params.campaignId || !params.name)
                    return errorResponse('campaignId and name required');
                const result = await createAdGroup({
                    campaignId: params.campaignId,
                    name: params.name,
                    cpcBidMicros: params.cpcBidMicros,
                    type: params.type,
                    customerId: params.customerId,
                });
                return NextResponse.json(result, { status: 201 });
            }

            case 'update_ad_group_bid': {
                if (!params.adGroupId || !params.cpcBidMicros)
                    return errorResponse('adGroupId and cpcBidMicros required');
                await updateAdGroupBid(params.adGroupId, params.cpcBidMicros, params.customerId);
                return NextResponse.json({ ok: true });
            }

            // ---- Ads ----
            case 'create_ad': {
                if (!params.adGroupId || !params.headlines || !params.descriptions || !params.finalUrls)
                    return errorResponse('adGroupId, headlines, descriptions, finalUrls required');
                const result = await createResponsiveSearchAd({
                    adGroupId: params.adGroupId,
                    headlines: params.headlines,
                    descriptions: params.descriptions,
                    finalUrls: params.finalUrls,
                    path1: params.path1,
                    path2: params.path2,
                    customerId: params.customerId,
                });
                return NextResponse.json(result, { status: 201 });
            }

            case 'list_ads': {
                if (!params.adGroupId) return errorResponse('adGroupId required');
                const ads = await listAds(params.adGroupId, params.customerId);
                return NextResponse.json({ ads });
            }

            // ---- Keywords ----
            case 'add_keywords': {
                if (!params.adGroupId || !params.keywords)
                    return errorResponse('adGroupId and keywords required');
                const result = await addKeywords({
                    adGroupId: params.adGroupId,
                    keywords: params.keywords,
                    customerId: params.customerId,
                });
                return NextResponse.json(result, { status: 201 });
            }

            case 'add_negative_keywords': {
                if (!params.campaignId || !params.keywords)
                    return errorResponse('campaignId and keywords required');
                const result = await addNegativeKeywords({
                    campaignId: params.campaignId,
                    keywords: params.keywords,
                    customerId: params.customerId,
                });
                return NextResponse.json(result, { status: 201 });
            }

            default:
                return errorResponse(
                    `Unknown action: ${action}. Valid: list_campaigns, get_campaign, create_campaign, update_status, update_budget, list_ad_groups, create_ad_group, update_ad_group_bid, create_ad, list_ads, add_keywords, add_negative_keywords`,
                    400
                );
        }
    } catch (error) {
        console.error('[Google Ads API] Error:', error);
        return errorResponse(
            error instanceof Error ? error.message : 'Internal error',
            500
        );
    }
}
