/** @type {import('next').NextConfig} */
const isExport = process.env.NEXT_OUTPUT === 'export';
const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

const nextConfig = isExport
  ? {
      // Static export served by the FastAPI backend (single-service deploy)
      output: 'export',
      trailingSlash: true,
    }
  : {
      // Dev / separate-service mode: proxy API calls to the backend
      async rewrites() {
        return [
          {
            source: '/api/:path*',
            destination: `${BACKEND_URL}/api/:path*`,
          },
        ];
      },
    };

module.exports = nextConfig;
