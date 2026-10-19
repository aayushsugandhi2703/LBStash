// In compose the proxy routes /api/* to the gateway; this rewrite gives `next dev` and `next start` the same same-origin paths.
const GATEWAY_URL = process.env.GATEWAY_URL ?? 'http://localhost:3000';

/** @type {import('next').NextConfig} */
export default {
  output: 'standalone',
  reactStrictMode: true,
  poweredByHeader: false,
  async rewrites() {
    return [{ source: '/api/:path*', destination: `${GATEWAY_URL}/:path*` }];
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
