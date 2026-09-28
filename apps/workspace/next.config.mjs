/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Lets a local production build run beside `next dev` without sharing .next.
  distDir: process.env.NEXT_DIST_DIR || '.next',
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
