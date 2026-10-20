/** @type {import('next').NextConfig} */
const backend = (process.env.API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      { source: "/api/research/v2/:path*", destination: `${backend}/api/research/v2/:path*` }
    ];
  }
};
module.exports = nextConfig;
