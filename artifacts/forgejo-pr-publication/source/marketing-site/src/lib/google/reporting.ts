/**
 * CodeTether Google Ads Reporting
 *
 * GAQL-based reporting for campaign, ad group, ad, and search term metrics.
 * Returns data compatible with the Thompson Sampling optimizer.
 *
 * @module lib/google/reporting
 */

import { getCustomer, microsToCents, microsToDollars } from './client';

// ============================================================================
// Types
// ============================================================================

export interface CampaignMetrics {
    campaignId: string;
    campaignName: string;
    status: string;
    channelType: string;
    impressions: number;
    clicks: number;
    ctr: number;
    avgCpcMicros: number;
    costMicros: number;
    conversions: number;
    conversionsValue: number;
    /** Cost in cents for Thompson Sampling integration */
    costCents: number;
    /** Revenue in cents for Thompson Sampling integration */
    revenueCents: number;
    date?: string;
}

export interface AdGroupMetrics {
    adGroupId: string;
    adGroupName: string;
    campaignId: string;
    status: string;
    impressions: number;
    clicks: number;
    ctr: number;
    avgCpcMicros: number;
    costMicros: number;
    conversions: number;
    conversionsValue: number;
}

export interface SearchTermMetrics {
    searchTerm: string;
    campaignId: string;
    adGroupId: string;
    impressions: number;
    clicks: number;
    costMicros: number;
    conversions: number;
}

export interface AccountSummary {
    impressions: number;
    clicks: number;
    ctr: number;
    avgCpcMicros: number;
    costMicros: number;
    conversions: number;
    conversionsValue: number;
    costDollars: number;
    roas: number;
}

// ============================================================================
// Campaign Report
// ============================================================================

/**
 * Get campaign-level performance report
 */
export async function getCampaignReport(params: {
    startDate: string; // YYYY-MM-DD
    endDate: string;
    customerId?: string;
}): Promise<CampaignMetrics[]> {
    const customer = getCustomer(params.customerId);

    const rows = await customer.query(`
        SELECT
            campaign.id,
            campaign.name,
            campaign.status,
            campaign.advertising_channel_type,
            metrics.impressions,
            metrics.clicks,
            metrics.ctr,
            metrics.average_cpc,
            metrics.cost_micros,
            metrics.conversions,
            metrics.conversions_value,
            segments.date
        FROM campaign
        WHERE segments.date BETWEEN '${params.startDate}' AND '${params.endDate}'
            AND campaign.status != 'REMOVED'
        ORDER BY metrics.cost_micros DESC
    `);

    return rows.map((row: any) => ({
        campaignId: String(row.campaign.id),
        campaignName: row.campaign.name,
        status: row.campaign.status,
        channelType: row.campaign.advertising_channel_type,
        impressions: Number(row.metrics.impressions) || 0,
        clicks: Number(row.metrics.clicks) || 0,
        ctr: Number(row.metrics.ctr) || 0,
        avgCpcMicros: Number(row.metrics.average_cpc) || 0,
        costMicros: Number(row.metrics.cost_micros) || 0,
        conversions: Number(row.metrics.conversions) || 0,
        conversionsValue: Number(row.metrics.conversions_value) || 0,
        costCents: microsToCents(Number(row.metrics.cost_micros) || 0),
        revenueCents: Math.round((Number(row.metrics.conversions_value) || 0) * 100),
        date: row.segments?.date,
    }));
}

// ============================================================================
// Ad Group Report
// ============================================================================

/**
 * Get ad group-level performance report
 */
export async function getAdGroupReport(params: {
    startDate: string;
    endDate: string;
    campaignId?: string;
    customerId?: string;
}): Promise<AdGroupMetrics[]> {
    const customer = getCustomer(params.customerId);

    let whereClause = `segments.date BETWEEN '${params.startDate}' AND '${params.endDate}'`;
    if (params.campaignId) {
        const cid = params.customerId ?? process.env.GOOGLE_ADS_CUSTOMER_ID!;
        whereClause += ` AND ad_group.campaign = 'customers/${cid}/campaigns/${params.campaignId}'`;
    }

    const rows = await customer.query(`
        SELECT
            ad_group.id,
            ad_group.name,
            ad_group.campaign,
            ad_group.status,
            metrics.impressions,
            metrics.clicks,
            metrics.ctr,
            metrics.average_cpc,
            metrics.cost_micros,
            metrics.conversions,
            metrics.conversions_value
        FROM ad_group
        WHERE ${whereClause}
        ORDER BY metrics.cost_micros DESC
    `);

    return rows.map((row: any) => ({
        adGroupId: String(row.ad_group.id),
        adGroupName: row.ad_group.name,
        campaignId: row.ad_group.campaign?.split('/').pop() ?? '',
        status: row.ad_group.status,
        impressions: Number(row.metrics.impressions) || 0,
        clicks: Number(row.metrics.clicks) || 0,
        ctr: Number(row.metrics.ctr) || 0,
        avgCpcMicros: Number(row.metrics.average_cpc) || 0,
        costMicros: Number(row.metrics.cost_micros) || 0,
        conversions: Number(row.metrics.conversions) || 0,
        conversionsValue: Number(row.metrics.conversions_value) || 0,
    }));
}

// ============================================================================
// Search Terms Report
// ============================================================================

/**
 * Get search terms report (what people actually typed)
 */
export async function getSearchTermsReport(params: {
    startDate: string;
    endDate: string;
    campaignId?: string;
    customerId?: string;
}): Promise<SearchTermMetrics[]> {
    const customer = getCustomer(params.customerId);

    let whereClause = `segments.date BETWEEN '${params.startDate}' AND '${params.endDate}'`;
    if (params.campaignId) {
        const cid = params.customerId ?? process.env.GOOGLE_ADS_CUSTOMER_ID!;
        whereClause += ` AND search_term_view.campaign = 'customers/${cid}/campaigns/${params.campaignId}'`;
    }

    const rows = await customer.query(`
        SELECT
            search_term_view.search_term,
            segments.campaign,
            segments.ad_group,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions
        FROM search_term_view
        WHERE ${whereClause}
        ORDER BY metrics.impressions DESC
        LIMIT 200
    `);

    return rows.map((row: any) => ({
        searchTerm: row.search_term_view.search_term,
        campaignId: row.segments?.campaign?.split('/').pop() ?? '',
        adGroupId: row.segments?.ad_group?.split('/').pop() ?? '',
        impressions: Number(row.metrics.impressions) || 0,
        clicks: Number(row.metrics.clicks) || 0,
        costMicros: Number(row.metrics.cost_micros) || 0,
        conversions: Number(row.metrics.conversions) || 0,
    }));
}

// ============================================================================
// Account Summary
// ============================================================================

/**
 * Get account-level summary for a date range
 */
export async function getAccountSummary(params: {
    startDate: string;
    endDate: string;
    customerId?: string;
}): Promise<AccountSummary> {
    const customer = getCustomer(params.customerId);

    const rows = await customer.query(`
        SELECT
            metrics.impressions,
            metrics.clicks,
            metrics.ctr,
            metrics.average_cpc,
            metrics.cost_micros,
            metrics.conversions,
            metrics.conversions_value
        FROM customer
        WHERE segments.date BETWEEN '${params.startDate}' AND '${params.endDate}'
    `);

    // Aggregate across date segments
    let impressions = 0, clicks = 0, costMicros = 0, conversions = 0, conversionsValue = 0;

    for (const row of rows as any[]) {
        impressions += Number(row.metrics.impressions) || 0;
        clicks += Number(row.metrics.clicks) || 0;
        costMicros += Number(row.metrics.cost_micros) || 0;
        conversions += Number(row.metrics.conversions) || 0;
        conversionsValue += Number(row.metrics.conversions_value) || 0;
    }

    const ctr = impressions > 0 ? clicks / impressions : 0;
    const avgCpc = clicks > 0 ? costMicros / clicks : 0;
    const costDollars = microsToDollars(costMicros);
    const roas = costDollars > 0 ? conversionsValue / costDollars : 0;

    return {
        impressions,
        clicks,
        ctr,
        avgCpcMicros: Math.round(avgCpc),
        costMicros,
        conversions,
        conversionsValue,
        costDollars,
        roas,
    };
}

// ============================================================================
// Thompson Sampling Bridge
// ============================================================================

/**
 * Fetch campaign metrics and convert to CampaignArm format
 * for Thompson Sampling integration
 */
export async function getCampaignMetricsForOptimizer(params: {
    startDate: string;
    endDate: string;
    customerId?: string;
}): Promise<
    Array<{
        campaignId: string;
        campaignName: string;
        impressions: number;
        clicks: number;
        conversions: number;
        spendCents: number;
        revenueCents: number;
    }>
> {
    const metrics = await getCampaignReport(params);

    return metrics.map(m => ({
        campaignId: m.campaignId,
        campaignName: m.campaignName,
        impressions: m.impressions,
        clicks: m.clicks,
        conversions: Math.round(m.conversions),
        spendCents: m.costCents,
        revenueCents: m.revenueCents,
    }));
}
