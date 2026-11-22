/**
 * Facebook Video Ad Pipeline API
 *
 * End-to-end: Creatify video generation → Facebook upload → campaign creation.
 *
 * POST /api/facebook/video-pipeline
 *   action: "generate_and_launch"  - Generate video + upload to Facebook + create campaign
 *   action: "launch"               - Upload existing video URL to Facebook + create campaign
 *   action: "check_video"          - Check Facebook video processing status
 *   action: "report"               - Get video campaign performance
 *   action: "list"                 - List Facebook campaigns
 */

import { NextRequest, NextResponse } from 'next/server';
import {
    launchFacebookVideoAd,
    checkFacebookVideoStatus,
    getFacebookVideoReport,
    listCampaigns,
} from '@/lib/facebook';
import {
    generateVideoAd,
    generateCodetetherVideoAd,
    type ScriptStyle,
} from '@/lib/creatify/client';

function errorResponse(message: string, status = 400) {
    return NextResponse.json({ error: message }, { status });
}

export async function POST(request: NextRequest) {
    const key = request.headers.get('x-api-key');
    const expected = process.env.GOOGLE_ADS_INTERNAL_API_KEY;
    if (expected && key !== expected) {
        return errorResponse('Unauthorized', 401);
    }

    try {
        const body = await request.json();
        const { action, ...params } = body;

        switch (action) {
            // ==============================================================
            // Full pipeline: Generate video → Facebook campaign
            // ==============================================================
            case 'generate_and_launch': {
                // Step 1: Generate video with Creatify
                let videoUrl: string;

                if (params.creatifyVideoUrl) {
                    videoUrl = params.creatifyVideoUrl;
                } else {
                    let video;
                    if (params.scriptStyle) {
                        video = await generateCodetetherVideoAd(
                            params.scriptStyle as ScriptStyle,
                            params.aspectRatio ?? '1:1', // Square works well for FB/IG
                        );
                    } else {
                        if (!params.url)
                            return errorResponse(
                                'url, scriptStyle, or creatifyVideoUrl required',
                            );
                        video = await generateVideoAd({
                            url: params.url,
                            aspectRatio: params.aspectRatio ?? '1:1',
                            script: params.script,
                            waitForCompletion: true,
                        });
                    }

                    if (video.status !== 'done' || !video.video_url) {
                        return errorResponse(
                            `Video generation ${video.status}: ${video.error ?? 'not ready'}`,
                            video.status === 'failed' ? 422 : 202,
                        );
                    }
                    videoUrl = video.video_url;
                }

                // Step 2: Upload to Facebook + create campaign
                const result = await launchFacebookVideoAd({
                    videoUrl,
                    campaignName: params.campaignName,
                    dailyBudgetDollars: params.dailyBudgetDollars,
                    landingUrl: params.landingUrl ?? params.finalUrl,
                    message: params.message,
                    headline: params.headline,
                    ctaType: params.ctaType,
                    thumbnailUrl: params.thumbnailUrl,
                    targeting: params.targeting,
                    pageId: params.pageId,
                    accountId: params.accountId,
                });

                return NextResponse.json(
                    {
                        pipeline: 'facebook_video_launched',
                        ...result,
                        nextSteps: [
                            'Campaign created as PAUSED on Facebook',
                            'Review in Facebook Ads Manager',
                            'Enable campaign when ready to spend',
                            'Monitor with action: "report"',
                        ],
                    },
                    { status: 201 },
                );
            }

            // ==============================================================
            // Launch from existing video URL
            // ==============================================================
            case 'launch': {
                if (!params.videoUrl)
                    return errorResponse('videoUrl required');

                const result = await launchFacebookVideoAd({
                    videoUrl: params.videoUrl,
                    campaignName: params.campaignName,
                    dailyBudgetDollars: params.dailyBudgetDollars,
                    landingUrl: params.landingUrl ?? params.finalUrl,
                    message: params.message,
                    headline: params.headline,
                    ctaType: params.ctaType,
                    thumbnailUrl: params.thumbnailUrl,
                    targeting: params.targeting,
                    pageId: params.pageId,
                    accountId: params.accountId,
                });

                return NextResponse.json(
                    {
                        pipeline: 'facebook_video_launched',
                        ...result,
                        nextSteps: [
                            'Campaign created as PAUSED on Facebook',
                            'Review in Facebook Ads Manager',
                            'Enable campaign when ready to spend',
                        ],
                    },
                    { status: 201 },
                );
            }

            // ==============================================================
            // Check video processing status
            // ==============================================================
            case 'check_video': {
                if (!params.facebookVideoId)
                    return errorResponse('facebookVideoId required');

                const status = await checkFacebookVideoStatus(
                    params.facebookVideoId,
                );
                return NextResponse.json({ videoStatus: status });
            }

            // ==============================================================
            // Performance report
            // ==============================================================
            case 'report': {
                const report = await getFacebookVideoReport({
                    days: params.days,
                    campaignId: params.campaignId,
                    accountId: params.accountId,
                });
                return NextResponse.json({ report });
            }

            // ==============================================================
            // List campaigns
            // ==============================================================
            case 'list': {
                const campaigns = await listCampaigns(params.accountId);
                return NextResponse.json({ campaigns });
            }

            default:
                return errorResponse(
                    `Unknown action: ${action}. Valid: generate_and_launch, launch, check_video, report, list`,
                );
        }
    } catch (error) {
        console.error('[Facebook Video Pipeline] Error:', error);
        return errorResponse(
            error instanceof Error ? error.message : 'Internal error',
            500,
        );
    }
}
