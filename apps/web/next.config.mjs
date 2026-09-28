/** @type {import('next').NextConfig} */
const nextConfig = {
  // Lets a local production build run beside `next dev` without sharing .next.
  distDir: process.env.NEXT_DIST_DIR || '.next',
  reactStrictMode: true,
  transpilePackages: [
    '@platform/ui',
    '@platform/contracts',
    '@platform/config',
    '@platform/validation',
    '@platform/api-client',
    '@platform/auth',
    '@platform/permissions',
    '@platform/observability',
  ],
}

export default nextConfig
