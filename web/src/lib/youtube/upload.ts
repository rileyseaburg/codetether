/**
 * YouTube Video Upload Client
 *
 * Uploads videos to YouTube via the YouTube Data API v3,
 * so they can be used as Google Ads video assets.
 *
 * Required env vars:
 *   GOOGLE_ADS_CLIENT_ID      (shared OAuth app)
 *   GOOGLE_ADS_CLIENT_SECRET
 *   YOUTUBE_REFRESH_TOKEN      (or falls back to GOOGLE_ADS_REFRESH_TOKEN)
 *
 * @module lib/youtube/upload
 */

import { google } from 'googleapis';
import { Readable } from 'stream';

function getAuth() {
    const clientId = process.env.GOOGLE_ADS_CLIENT_ID;
    const clientSecret = process.env.GOOGLE_ADS_CLIENT_SECRET;
    const refreshToken =
        process.env.YOUTUBE_REFRESH_TOKEN ?? process.env.GOOGLE_ADS_REFRESH_TOKEN;

    if (!clientId || !clientSecret || !refreshToken) {
        throw new Error(
            'Missing YouTube/Google OAuth credentials. Set GOOGLE_ADS_CLIENT_ID, GOOGLE_ADS_CLIENT_SECRET, and YOUTUBE_REFRESH_TOKEN.',
        );
    }

    const oauth2 = new google.auth.OAuth2(clientId, clientSecret);
    oauth2.setCredentials({ refresh_token: refreshToken });
    return oauth2;
}

export interface UploadVideoParams {
    /** Video file as a Buffer */
    videoBuffer: Buffer;
    /** Video title on YouTube */
    title: string;
    /** Video description */
    description?: string;
    /** Tags for discoverability */
    tags?: string[];
    /** Privacy: unlisted is ideal for ad-only videos */
    privacyStatus?: 'public' | 'unlisted' | 'private';
    /** YouTube category ID (22 = People & Blogs, 28 = Science & Technology) */
    categoryId?: string;
}

export interface UploadResult {
    videoId: string;
    youtubeUrl: string;
    title: string;
    status: string;
}

/**
 * Upload a video buffer to YouTube.
 *
 * Returns the YouTube video ID, which can then be used with
 * `launchVideoAdFromYouTube()` to create a Google Ads campaign.
 */
export async function uploadVideoToYouTube(
    params: UploadVideoParams,
): Promise<UploadResult> {
    const auth = getAuth();
    const youtube = google.youtube({ version: 'v3', auth });

    const stream = Readable.from(params.videoBuffer);

    const response = await youtube.videos.insert({
        part: ['snippet', 'status'],
        requestBody: {
            snippet: {
                title: params.title,
                description:
                    params.description ??
                    'CodeTether AI-generated video ad. https://codetether.io',
                tags: params.tags ?? ['CodeTether', 'AI', 'automation'],
                categoryId: params.categoryId ?? '28', // Science & Technology
            },
            status: {
                privacyStatus: params.privacyStatus ?? 'unlisted',
            },
        },
        media: {
            body: stream,
        },
    });

    const videoId = response.data.id;
    if (!videoId) {
        throw new Error('YouTube upload succeeded but no video ID returned');
    }

    return {
        videoId,
        youtubeUrl: `https://www.youtube.com/watch?v=${videoId}`,
        title: params.title,
        status: response.data.status?.uploadStatus ?? 'uploaded',
    };
}

/**
 * Download a video from a URL and return it as a Buffer.
 * Used to bridge Creatify video_url → YouTube upload.
 */
export async function downloadVideo(videoUrl: string): Promise<Buffer> {
    const res = await fetch(videoUrl);
    if (!res.ok) {
        throw new Error(`Failed to download video: ${res.status} ${res.statusText}`);
    }
    const arrayBuffer = await res.arrayBuffer();
    return Buffer.from(arrayBuffer);
}

/**
 * Download a Creatify video and upload it to YouTube.
 *
 * This is the bridge between Creatify generation and Google Ads:
 * Creatify video_url → download → YouTube upload → videoId → Google Ads asset
 */
export async function uploadCreatifyVideoToYouTube(params: {
    /** The Creatify video_url from a completed generation */
    creatifyVideoUrl: string;
    /** Title for the YouTube video */
    title: string;
    /** Description */
    description?: string;
    /** Tags */
    tags?: string[];
}): Promise<UploadResult> {
    const videoBuffer = await downloadVideo(params.creatifyVideoUrl);

    return uploadVideoToYouTube({
        videoBuffer,
        title: params.title,
        description: params.description,
        tags: params.tags,
        privacyStatus: 'unlisted', // Ad-only, not public
    });
}
