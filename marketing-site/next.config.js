/** @type {import('next').NextConfig} */
const nextConfig = {
    output: 'standalone',
    images: {
        unoptimized: true,
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
