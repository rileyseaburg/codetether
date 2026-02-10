/**
 * CodeTether Self-Selling API - Page Assembly
 *
 * GET /api/optimization/assemble
 *   Returns optimized page variant selections for the current visitor.
 *   Uses Thompson Sampling to select the best variant for each slot.
 *
 * POST /api/optimization/assemble
 *   Records a conversion event for a session.
 *
 * This endpoint is called by the marketing site on every page load
 * to personalize the marketing page based on ad context and visitor signals.
 */

import { NextRequest, NextResponse } from 'next/server';
import { MarketingFunnelBrain, extractAdContext } from '@/lib/optimization';
import type { ConversionEventType } from '@/lib/optimization';

// Singleton FunnelBrain (in production, state would be in a database)
let funnelBrain: MarketingFunnelBrain | null = null;

function getFunnelBrain(): MarketingFunnelBrain {
  if (!funnelBrain) {
    funnelBrain = new MarketingFunnelBrain({ explorationRate: 0.05 });

    // Restore state from storage if available
    if (typeof globalThis !== 'undefined' && (globalThis as any).__funnelBrainState) {
      funnelBrain.importState((globalThis as any).__funnelBrainState);
    }
  }
  return funnelBrain;
}

function persistState(): void {
  if (funnelBrain && typeof globalThis !== 'undefined') {
    (globalThis as any).__funnelBrainState = funnelBrain.exportState();
  }
}

/**
 * GET /api/optimization/assemble?utm_source=...&utm_medium=...
 *
 * Assembles an optimized page for the visitor.
 */
export async function GET(request: NextRequest) {
  const searchParams = Object.fromEntries(request.nextUrl.searchParams);
  const headers: Record<string, string | undefined> = {
    referer: request.headers.get('referer') ?? undefined,
    referrer: request.headers.get('referrer') ?? undefined,
    'user-agent': request.headers.get('user-agent') ?? undefined,
  };

  const adContext = extractAdContext(searchParams, headers);

  // Generate session ID
  const sessionId = `cs_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;

  const brain = getFunnelBrain();
  const assembly = brain.assemblePage(sessionId, adContext);

  // Record impressions for all selected variants
  for (const selection of Object.values(assembly.slots)) {
    brain.recordImpression(selection.variantId);
  }

  persistState();

  return NextResponse.json({
    sessionId: assembly.sessionId,
    slots: assembly.slots,
    renderTimeMs: assembly.renderTimeMs,
    timestamp: assembly.timestamp,
  });
}

/**
 * POST /api/optimization/assemble
 *
 * Record a conversion event.
 *
 * Body: {
 *   sessionId: string,
 *   eventType: 'cta_click' | 'signup_complete' | 'subscription_start',
 *   variantIds: string[],
 *   valueCents?: number
 * }
 */
export async function POST(request: NextRequest) {
  const body = await request.json();

  const { sessionId, eventType, variantIds, valueCents = 0 } = body as {
    sessionId: string;
    eventType: 'cta_click' | 'signup_complete' | 'subscription_start';
    variantIds: string[];
    valueCents?: number;
  };

  if (!sessionId || !eventType || !Array.isArray(variantIds)) {
    return NextResponse.json(
      { error: 'sessionId, eventType, and variantIds[] are required' },
      { status: 400 }
    );
  }

  const validEvents: ConversionEventType[] = ['cta_click', 'signup_complete', 'subscription_start'];
  if (!validEvents.includes(eventType)) {
    return NextResponse.json(
      { error: `eventType must be one of: ${validEvents.join(', ')}` },
      { status: 400 }
    );
  }

  const brain = getFunnelBrain();
  brain.recordConversion(variantIds, eventType, valueCents);
  persistState();

  return NextResponse.json({ success: true, sessionId, eventType });
}
