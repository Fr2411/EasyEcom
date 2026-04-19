/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  async redirects() {
    return [
      {
        source: '/home',
        destination: '/dashboard',
        permanent: false
      },
      {
        source: '/products',
        destination: '/catalog',
        permanent: false
      },
      {
        source: '/inventory/products',
        destination: '/inventory',
        permanent: false
      }
    ];
  }
};

module.exports = nextConfig;
