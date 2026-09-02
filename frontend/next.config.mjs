/** @type {import('next').NextConfig} */
const nextConfig = {
  // Allows Hot Module Replacement (auto-refresh) from these IPs
  allowedDevOrigins: ['127.0.0.1', 'localhost', '10.241.75.32'],

  async rewrites() {
    // 🔥 UPGRADED: Uses your live server URL if deployed, or localhost if testing
    const backendUrl = process.env.BACKEND_URL || 'http://127.0.0.1:5000';

    return [
      {
        source: '/api/:path*',
        destination: `${backendUrl}/api/:path*`,
      },
    ]
  },
};

export default nextConfig;
