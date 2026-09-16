/** @type {import('next').NextConfig} */
const nextConfig = {
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
