/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  async redirects() {
    return [
      {
        source: '/home',
        destination: '/dashboard',
        permanent: false
      }
    ];
  }
};

module.exports = nextConfig;
