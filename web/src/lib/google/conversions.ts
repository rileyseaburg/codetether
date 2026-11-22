/**
 * CodeTether Google Ads Conversion Tracking
 *
 * Server-side conversion uploads with Enhanced Conversions support.
 * Integrates with the Thompson Sampling optimizer for closed-loop optimization.
 *
 * @module lib/google/conversions
 */

import crypto from 'crypto';
import { getCustomer } from './client';

// ============================================================================
// Types
// ============================================================================

export interface ConversionUpload {
    conversionAction: string;
    gclid?: string;
    conversionDateTime: string;
    conversionValue?: number;
    currencyCode?: string;
    orderId?: string;
    userData?: {
        email?: string;
        phone?: string;
        firstName?: string;
        lastName?: string;
    };
}

export interface ConversionResult {
    success: boolean;
    conversionsUploaded: number;
    error?: string;
}

// ============================================================================
// Helpers
// ============================================================================

function sha256(value: string): string {
    return crypto.createHash('sha256').update(value.toLowerCase().trim()).digest('hex');
}

function formatDateTime(date: Date = new Date()): string {
    // Google Ads requires: "yyyy-MM-dd HH:mm:ss+|-HH:mm"
    return date.toISOString().replace('T', ' ').substring(0, 19) + '+00:00';
}

// ============================================================================
// Upload conversions
// ============================================================================

/**
 * Upload click conversions to Google Ads
 */
export async function uploadConversions(
    conversions: ConversionUpload[],
    customerId?: string
): Promise<ConversionResult> {
    try {
        const cid = customerId ?? process.env.GOOGLE_ADS_CUSTOMER_ID;
        if (!cid) throw new Error('No Google Ads customer ID');

        const customer = getCustomer(cid);

        const clickConversions = conversions.map(conv => {
            const conversionAction = conv.conversionAction.includes('/')
                ? conv.conversionAction
                : `customers/${cid}/conversionActions/${conv.conversionAction}`;

            const entry: Record<string, unknown> = {
                conversion_action: conversionAction,
                conversion_date_time: conv.conversionDateTime,
                conversion_value: conv.conversionValue,
                currency_code: conv.currencyCode ?? 'USD',
            };

            if (conv.gclid) entry.gclid = conv.gclid;
            if (conv.orderId) entry.order_id = conv.orderId;

            // Enhanced conversion user data (hashed PII)
            if (conv.userData) {
                const identifiers: Record<string, string> = {};
                if (conv.userData.email) identifiers.hashed_email = sha256(conv.userData.email);
                if (conv.userData.phone) identifiers.hashed_phone_number = sha256(conv.userData.phone);
                if (conv.userData.firstName) identifiers.hashed_first_name = sha256(conv.userData.firstName);
                if (conv.userData.lastName) identifiers.hashed_last_name = sha256(conv.userData.lastName);

                if (Object.keys(identifiers).length > 0) {
                    entry.user_identifiers = [identifiers];
                }
            }

            return entry;
        });

        const response = await customer.conversionUploads.uploadClickConversions({
            customer_id: cid,
            conversions: clickConversions,
            partial_failure: true,
            validate_only: false,
        } as any);

        let successCount = clickConversions.length;
        if (response.partial_failure_error) {
            const failCount = response.partial_failure_error.details?.length ?? 0;
            successCount = clickConversions.length - failCount;
        }

        return { success: true, conversionsUploaded: successCount };
    } catch (error) {
        return {
            success: false,
            conversionsUploaded: 0,
            error: error instanceof Error ? error.message : String(error),
        };
    }
}

/**
 * Track a CodeTether funnel conversion (signup, trial, subscription)
 *
 * Called when user converts on the marketing site. Reports back to
 * Google Ads so the algorithm can optimize toward real conversions.
 */
export async function trackCodetetherConversion(params: {
    eventType: 'signup' | 'trial_start' | 'subscription';
    email: string;
    gclid?: string;
    valueDollars: number;
    orderId?: string;
    conversionActionId?: string;
    customerId?: string;
}): Promise<ConversionResult> {
    const conversionActionId =
        params.conversionActionId ??
        process.env.GOOGLE_ADS_CONVERSION_ACTION_ID;

    if (!conversionActionId) {
        return {
            success: false,
            conversionsUploaded: 0,
            error: 'No conversion action ID configured',
        };
    }

    return uploadConversions(
        [
            {
                conversionAction: conversionActionId,
                gclid: params.gclid,
                conversionDateTime: formatDateTime(),
                conversionValue: params.valueDollars,
                currencyCode: 'USD',
                orderId: params.orderId ?? `ct-${params.eventType}-${Date.now()}`,
                userData: { email: params.email },
            },
        ],
        params.customerId
    );
}

/**
 * List available conversion actions
 */
export async function listConversionActions(customerId?: string) {
    const customer = getCustomer(customerId);

    const results = await customer.query(`
        SELECT
            conversion_action.id,
            conversion_action.name,
            conversion_action.category,
            conversion_action.status
        FROM conversion_action
        WHERE conversion_action.status = 'ENABLED'
        ORDER BY conversion_action.name
    `);

    return results.map((row: any) => ({
        id: String(row.conversion_action.id),
        name: row.conversion_action.name,
        category: row.conversion_action.category,
        status: row.conversion_action.status,
    }));
}
