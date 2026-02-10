/**
 * Video Ad Pipeline API
 *
 * Full end-to-end: Creatify video generation → YouTube upload → Google Ads campaign.
 *
 * POST /api/google/video-pipeline
 *   action: "generate"            - Generate a video with Creatify (returns videoId to poll)
 *   action: "check_status"        - Check Creatify video generation status
 *   action: "generate_and_launch" - Generate video → upload to YouTube → create Google Ads campaign (all-in-one)
 *   action: "launch"              - Take an existing YouTube video ID → create Google Ads campaign
 *   action: "report"              - Get video campaign performance
 *   action: "list"                - List all video ads across campaigns
 *   action: "credits"             - Check remaining Creatify credits
 */

import { NextRequest, NextResponse } from 'next/server';
import {
    launchVideoAdFromYouTube,
    listVideoAds,
    getVideoReport,
} from '@/lib/google/videoAds';
import {
    generateVideoAd,
    generateCodetetherVideoAd,
    getVideo,
    getRemainingCredits,
    type ScriptStyle,
} from '@/lib/creatify/client';
import { uploadCreatifyVideoToYouTube } from '@/lib/youtube/upload';

function errorResponse(message: string, status = 400) {
    return NextResponse.json({ error: message }, { status });
}

export async function POST(request: NextRequest) {
    // Check API key for write operations
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
            // Step 1: Generate video with Creatify
            // ==============================================================
            case 'generate': {
                let video;

                if (params.scriptStyle) {
                    // Pre-configured CodeTether ad
                    video = await generateCodetetherVideoAd(
                        params.scriptStyle as ScriptStyle,
                        params.aspectRatio ?? '16:9',
                    );
                } else {
                    // Custom URL-based generation
                    if (!params.url)
                        return errorResponse('url or scriptStyle required');

                    video = await generateVideoAd({
                        url: params.url,
                        aspectRatio: params.aspectRatio ?? '16:9',
                        script: params.script,
                        voiceId: params.voiceId,
                        avatarId: params.avatarId,
                        waitForCompletion: params.waitForCompletion ?? true,
                    });
                }

                return NextResponse.json(
                    {
                        pipeline: 'video_generated',
                        creatifyVideoId: video.id,
                        status: video.status,
                        videoUrl: video.video_url,
                        thumbnailUrl: video.thumbnail_url,
                        nextSteps:
                            video.status === 'done'
                                ? [
                                    'Video ready! Use action: "generate_and_launch" or upload to YouTube manually.',
                                    'Or re-call with action: "launch" and a youtubeVideoId.',
                                ]
                                : [
                                    `Video is ${video.status}. Poll with action: "check_status" and creatifyVideoId.`,
                                ],
                    },
                    { status: 201 },
                );
            }

            // ==============================================================
            // Step 1b: Check Creatify generation status
            // ==============================================================
            case 'check_status': {
                if (!params.creatifyVideoId)
                    return errorResponse('creatifyVideoId required');

                const video = await getVideo(params.creatifyVideoId);

                return NextResponse.json({
                    creatifyVideoId: video.id,
                    status: video.status,
                    videoUrl: video.video_url,
                    thumbnailUrl: video.thumbnail_url,
                    duration: video.duration,
                });
            }

            // ==============================================================
            // Full pipeline: Generate → YouTube → Google Ads (all-in-one)
            // ==============================================================
            case 'generate_and_launch': {
                // Step 1: Generate video
                let video;
                if (params.scriptStyle) {
                    video = await generateCodetetherVideoAd(
                        params.scriptStyle as ScriptStyle,
                        params.aspectRatio ?? '16:9',
                    );
                } else if (params.creatifyVideoUrl) {
                    // Already have a Creatify video URL, skip generation
                    video = { id: 'existing', status: 'done' as const, video_url: params.creatifyVideoUrl };
                } else {
                    if (!params.url)
                        return errorResponse(
                            'url, scriptStyle, or creatifyVideoUrl required',
                        );
                    video = await generateVideoAd({
                        url: params.url,
                        aspectRatio: params.aspectRatio ?? '16:9',
                        script: params.script,
                        voiceId: params.voiceId,
                        avatarId: params.avatarId,
                        waitForCompletion: true,
                    });
                }

                if (video.status !== 'done' || !video.video_url) {
                    return errorResponse(
                        `Video generation ${video.status}: ${video.error ?? 'not ready'}`,
                        video.status === 'failed' ? 422 : 202,
                    );
                }

                // Step 2: Upload to YouTube
                const ytTitle =
                    params.campaignName ??
                    `CodeTether Video Ad ${new Date().toISOString().split('T')[0]}`;

                const ytResult = await uploadCreatifyVideoToYouTube({
                    creatifyVideoUrl: video.video_url,
                    title: ytTitle,
                    description:
                        params.videoDescription ??
                        'AI-generated video ad for CodeTether. https://codetether.io',
                    tags: ['CodeTether', 'AI', 'automation', 'video ad'],
                });

                // Step 3: Create Google Ads campaign
                const campaign = await launchVideoAdFromYouTube({
                    youtubeVideoId: ytResult.videoId,
                    campaignName: ytTitle,
                    dailyBudgetDollars: params.dailyBudgetDollars ?? 25,
                    finalUrl: params.finalUrl ?? 'https://codetether.run',
                    displayUrl: params.displayUrl ?? 'codetether.run',
                    headline:
                        params.headline ?? 'AI Agents That Actually Deliver',
                    callToAction: params.callToAction ?? 'Start Free',
                    adType: params.adType ?? 'IN_STREAM',
                    customerId: params.customerId,
                });

                return NextResponse.json(
                    {
                        pipeline: 'full_pipeline_complete',
                        creatify: {
                            videoId: video.id,
                            videoUrl: video.video_url,
                        },
                        youtube: {
                            videoId: ytResult.videoId,
                            youtubeUrl: ytResult.youtubeUrl,
                        },
                        googleAds: {
                            campaignId: campaign.campaignId,
                            campaignResourceName: campaign.campaignResourceName,
                            adGroupId: campaign.adGroupId,
                            adResourceName: campaign.adResourceName,
                            status: campaign.status,
                        },
                        nextSteps: [
                            'Campaign created as PAUSED',
                            'Review in Google Ads UI',
                            'Enable campaign when ready to spend',
                            'Monitor with action: "report"',
                        ],
                    },
                    { status: 201 },
                );
            }

            // ==============================================================
            // Launch from existing YouTube video
            // ==============================================================
            case 'launch': {
                if (!params.youtubeVideoId)
                    return errorResponse('youtubeVideoId required');

                const result = await launchVideoAdFromYouTube({
                    youtubeVideoId: params.youtubeVideoId,
                    campaignName:
                        params.campaignName ??
                        `CodeTether Video Ad ${new Date().toISOString().split('T')[0]}`,
                    dailyBudgetDollars: params.dailyBudgetDollars ?? 25,
                    finalUrl: params.finalUrl ?? 'https://codetether.run',
                    displayUrl: params.displayUrl ?? 'codetether.run',
                    headline:
                        params.headline ?? 'AI Agents That Actually Deliver',
                    callToAction: params.callToAction ?? 'Start Free',
                    adType: params.adType ?? 'IN_STREAM',
                    customerId: params.customerId,
                });

                return NextResponse.json(
                    {
                        pipeline: 'video_ad_launched',
                        ...result,
                        nextSteps: [
                            'Review campaign in Google Ads UI',
                            'Enable campaign when ready to spend',
                            'Monitor with action: "report"',
                        ],
                    },
                    { status: 201 },
                );
            }

            // ==============================================================
            // List & Report
            // ==============================================================
            case 'list': {
                const ads = await listVideoAds({
                    adGroupId: params.adGroupId,
                    campaignId: params.campaignId,
                    customerId: params.customerId,
                });
                return NextResponse.json({ videoAds: ads });
            }

            case 'report': {
                const end = new Date();
                const start = new Date();
                start.setDate(start.getDate() - (params.days ?? 30));

                const report = await getVideoReport({
                    startDate:
                        params.startDate ?? start.toISOString().split('T')[0],
                    endDate:
                        params.endDate ?? end.toISOString().split('T')[0],
                    customerId: params.customerId,
                });

                return NextResponse.json({ report });
            }

            // ==============================================================
            // Credits check
            // ==============================================================
            case 'credits': {
                const credits = await getRemainingCredits();
                return NextResponse.json({ remainingCredits: credits });
            }

            default:
                return errorResponse(
                    `Unknown action: ${action}. Valid: generate, check_status, generate_and_launch, launch, list, report, credits`,
                );
        }
    } catch (error) {
        console.error('[Video Pipeline] Error:', error);
        return errorResponse(
            error instanceof Error ? error.message : 'Internal error',
            500,
        );
    }
}
