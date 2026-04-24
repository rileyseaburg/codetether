/** @type {import('next').NextConfig} */
const nextConfig = {
    output: 'standalone',
    turbopack: {
        root: __dirname,
    },
    images: {
        // Enable Next.js image optimization for WebP/AVIF, lazy loading, blur placeholders
        formats: ['image/avif', 'image/webp'],
        deviceSizes: [640, 750, 828, 1080, 1200, 1920, 2048],
        imageSizes: [16, 32, 48, 64, 96, 128, 256, 384],
        // Add any external image domains here if needed
        remotePatterns: [],
    },
    async redirects() {
        return [
            {
                source: '/docs',
                destination: 'https://docs.codetether.run',
                permanent: true
            },
        ]
    },
    async rewrites() {
        const cognitionApi = process.env.COGNITION_API_BACKEND
        const a2aApi = process.env.A2A_API_BACKEND
        const rewrites = []

        if (cognitionApi) {
            rewrites.push(
                {
                    source: '/api/cognition/:path*',
                    destination: `${cognitionApi}/v1/cognition/:path*`,
                },
                {
                    source: '/api/swarm/:path*',
                    destination: `${cognitionApi}/v1/swarm/:path*`,
                },
            )
        } else {
            console.warn(
                '[next.config] COGNITION_API_BACKEND not set.',
                'Cognition API rewrites are disabled.',
            )
        }

        if (a2aApi) {
            rewrites.push(
                {
                source: '/api/v1/:path*',
                destination: `${a2aApi}/v1/:path*`,
                },
                // Tenant API proxy - strips /tenant prefix so /api/tenant/v1/* → /v1/*
                {
                    source: '/api/tenant/:path*',
                    destination: `${a2aApi}/:path*`,
                },
            )
        } else {
            console.warn(
                '[next.config] A2A_API_BACKEND not set.',
                'A2A API rewrites /api/v1/* and /api/tenant/* are disabled.',
            )
        }

        return rewrites
    },
}

module.exports = nextConfig
