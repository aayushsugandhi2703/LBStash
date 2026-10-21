// In compose nginx routes /api/* to the gateway; this rewrite gives `next dev` and `next start` the same same-origin paths.
const GATEWAY_URL = process.env.GATEWAY_URL ?? 'http://localhost:3000';

/** @type {import('next').NextConfig} */
export default {
  output: 'standalone',
  reactStrictMode: true,
  poweredByHeader: false,
  images: { unoptimized: true }, // no next/image in the app; keeps the sharp/libvips binaries out of the image
  async rewrites() {
    return [{ source: '/api/:path*', destination: `${GATEWAY_URL}/:path*` }];
  },
  // The pages were merged (Money, Budget, Forecast) and Add credit went (Telegram logs money in): old addresses and the links Now builds still land. Query strings carry over.
  async redirects() {
    return [
      { source: '/transactions', destination: '/money', permanent: false },
      { source: '/transactions/unread', destination: '/money/unread', permanent: false },
      { source: '/repeats', destination: '/money/repeats', permanent: false },
      { source: '/plan', destination: '/budget', permanent: false },
      { source: '/limits', destination: '/budget/limits', permanent: false },
      { source: '/trends', destination: '/forecast', permanent: false },
      { source: '/credit', destination: '/', permanent: false },
      { source: '/welcome', destination: '/', permanent: false },
    ];
  },
  async headers() {
    return [{
      source: '/:path*',
      headers: [
        { key: 'X-Content-Type-Options', value: 'nosniff' },
        { key: 'Referrer-Policy', value: 'no-referrer' },
        { key: 'X-Frame-Options', value: 'DENY' },
        { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=(), publickey-credentials-get=(self), publickey-credentials-create=(self)' },
        { key: 'Cache-Control', value: 'no-store' },
      ],
    }];
  },
};
