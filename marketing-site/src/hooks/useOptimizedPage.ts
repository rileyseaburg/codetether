/**
 * useOptimizedPage - React hook for Thompson Sampling page optimization
 *
 * This hook fetches the optimized page assembly from the API,
 * tracks which variants were shown, and reports conversions.
 *
 * Usage:
 * ```tsx
 * function Hero() {
 *   const { getSlot, trackConversion, isLoaded } = useOptimizedPage();
 *   const headline = getSlot('hero_headline');
 *
 *   return (
 *     <h1>{headline?.content.headline ?? 'Default Headline'}</h1>
 *     <button onClick={() => trackConversion('cta_click')}>
 *       {headline?.content.cta ?? 'Get Started'}
 *     </button>
 *   );
 * }
 * ```
 */

'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import type { MarketingSlot, SlotSelection } from '@/lib/optimization/types';

interface OptimizedPageState {
    sessionId: string | null;
    slots: Record<string, SlotSelection>;
    isLoaded: boolean;
    error: string | null;
}

interface UseOptimizedPageReturn {
    /** Get the selected variant for a slot */
    getSlot: (slot: MarketingSlot) => SlotSelection | null;
    /** Track a conversion event */
    trackConversion: (eventType: 'cta_click' | 'signup_complete' | 'subscription_start', valueCents?: number) => void;
    /** Session ID for this page view */
    sessionId: string | null;
    /** Whether the optimized assembly has loaded */
    isLoaded: boolean;
    /** Error message if assembly failed */
    error: string | null;
}

export function useOptimizedPage(): UseOptimizedPageReturn {
    const [state, setState] = useState<OptimizedPageState>({
        sessionId: null,
        slots: {},
        isLoaded: false,
        error: null,
    });

    const hasTrackedRef = useRef(false);

    useEffect(() => {
        // Build URL from current page's search params
        const url = new URL('/api/optimization/assemble', window.location.origin);
        const currentParams = new URLSearchParams(window.location.search);
        currentParams.forEach((value, key) => url.searchParams.set(key, value));

        fetch(url.toString())
            .then(res => {
                if (!res.ok) throw new Error(`Assembly failed: ${res.status}`);
                return res.json();
            })
            .then(data => {
                setState({
                    sessionId: data.sessionId,
                    slots: data.slots ?? {},
                    isLoaded: true,
                    error: null,
                });
            })
            .catch(err => {
                // Fail silently - page shows defaults
                setState(prev => ({ ...prev, isLoaded: true, error: err.message }));
            });
    }, []);

    const getSlot = useCallback(
        (slot: MarketingSlot): SlotSelection | null => {
            return state.slots[slot] ?? null;
        },
        [state.slots]
    );

    const trackConversion = useCallback(
        (eventType: 'cta_click' | 'signup_complete' | 'subscription_start', valueCents: number = 0) => {
            if (!state.sessionId || hasTrackedRef.current) return;

            const variantIds = Object.values(state.slots).map(s => s.variantId);
            if (variantIds.length === 0) return;

            // Fire-and-forget
            fetch('/api/optimization/assemble', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    sessionId: state.sessionId,
                    eventType,
                    variantIds,
                    valueCents,
                }),
            }).catch(() => {
                // Silently fail - don't block user experience
            });

            if (eventType === 'signup_complete') {
                hasTrackedRef.current = true;
            }
        },
        [state.sessionId, state.slots]
    );

    return {
        getSlot,
        trackConversion,
        sessionId: state.sessionId,
        isLoaded: state.isLoaded,
        error: state.error,
    };
}
