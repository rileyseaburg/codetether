/**
 * Google Ads Conversion Tracking API
 *
 * POST /api/google/conversions           - Upload conversion(s)
 * POST /api/google/conversions?action=track  - Track a CodeTether funnel event
 * GET  /api/google/conversions           - List conversion actions
 */

import { NextRequest, NextResponse } from 'next/server';
import {
    uploadConversions,
    trackCodetetherConversion,
    listConversionActions,
} from '@/lib/google/conversions';

export async function GET() {
    try {
        const actions = await listConversionActions();
        return NextResponse.json({ conversionActions: actions });
    } catch (error) {
        console.error('[Google Ads Conversions] Error:', error);
        return NextResponse.json(
            { error: error instanceof Error ? error.message : 'Internal error' },
            { status: 500 }
        );
    }
}

export async function POST(request: NextRequest) {
    try {
        const body = await request.json();
        const { action } = body;

        if (action === 'track') {
            // Track a CodeTether-specific conversion
            const { eventType, email, gclid, valueDollars, orderId, conversionActionId } = body;

            if (!eventType || !email) {
                return NextResponse.json(
                    { error: 'eventType and email required' },
                    { status: 400 }
                );
            }

            const result = await trackCodetetherConversion({
                eventType,
                email,
                gclid,
                valueDollars: valueDollars ?? 0,
                orderId,
                conversionActionId,
            });

            return NextResponse.json(result);
        }

        // Raw conversion upload
        if (!body.conversions || !Array.isArray(body.conversions)) {
            return NextResponse.json(
                { error: 'conversions array required' },
                { status: 400 }
            );
        }

        const result = await uploadConversions(body.conversions, body.customerId);
        return NextResponse.json(result);
    } catch (error) {
        console.error('[Google Ads Conversions] Error:', error);
        return NextResponse.json(
            { error: error instanceof Error ? error.message : 'Internal error' },
            { status: 500 }
        );
    }
}
