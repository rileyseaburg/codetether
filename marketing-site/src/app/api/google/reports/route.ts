/**
 * Google Ads Reporting API
 *
 * GET  /api/google/reports?type=campaigns&startDate=...&endDate=...
 * GET  /api/google/reports?type=adgroups&campaignId=...
 * GET  /api/google/reports?type=search_terms&campaignId=...
 * GET  /api/google/reports?type=summary
 * GET  /api/google/reports?type=optimizer  (Thompson Sampling bridge)
 */

import { NextRequest, NextResponse } from 'next/server';
import {
    getCampaignReport,
    getAdGroupReport,
    getSearchTermsReport,
    getAccountSummary,
    getCampaignMetricsForOptimizer,
} from '@/lib/google/reporting';

function defaultDateRange() {
    const end = new Date();
    const start = new Date();
    start.setDate(start.getDate() - 30);
    return {
        startDate: start.toISOString().split('T')[0],
        endDate: end.toISOString().split('T')[0],
    };
}

export async function GET(request: NextRequest) {
    const { searchParams } = new URL(request.url);
    const reportType = searchParams.get('type') ?? 'summary';
    const startDate = searchParams.get('startDate') ?? defaultDateRange().startDate;
    const endDate = searchParams.get('endDate') ?? defaultDateRange().endDate;
    const campaignId = searchParams.get('campaignId') ?? undefined;
    const customerId = searchParams.get('customerId') ?? undefined;

    try {
        switch (reportType) {
            case 'campaigns': {
                const data = await getCampaignReport({ startDate, endDate, customerId });
                return NextResponse.json({ report: 'campaigns', startDate, endDate, data });
            }

            case 'adgroups': {
                const data = await getAdGroupReport({
                    startDate,
                    endDate,
                    campaignId,
                    customerId,
                });
                return NextResponse.json({ report: 'adgroups', startDate, endDate, data });
            }

            case 'search_terms': {
                const data = await getSearchTermsReport({
                    startDate,
                    endDate,
                    campaignId,
                    customerId,
                });
                return NextResponse.json({ report: 'search_terms', startDate, endDate, data });
            }

            case 'summary': {
                const data = await getAccountSummary({ startDate, endDate, customerId });
                return NextResponse.json({ report: 'summary', startDate, endDate, data });
            }

            case 'optimizer': {
                const data = await getCampaignMetricsForOptimizer({
                    startDate,
                    endDate,
                    customerId,
                });
                return NextResponse.json({ report: 'optimizer', startDate, endDate, data });
            }

            default:
                return NextResponse.json(
                    { error: `Unknown report type: ${reportType}. Valid: campaigns, adgroups, search_terms, summary, optimizer` },
                    { status: 400 }
                );
        }
    } catch (error) {
        console.error('[Google Ads Reports] Error:', error);
        return NextResponse.json(
            { error: error instanceof Error ? error.message : 'Internal error' },
            { status: 500 }
        );
    }
}
