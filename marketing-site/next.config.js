/** @type {import('next').NextConfig} */
const nextConfig = {
    output: 'standalone',
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
            {
                source: '/api',
                destination: 'https://api.codetether.run',
                permanent: true
            }
        ]
    }
}

module.exports = nextConfig
