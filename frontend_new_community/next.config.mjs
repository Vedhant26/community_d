/** @type {import('next').NextConfig} */
const nextConfig = {
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: process.env.NEXT_PUBLIC_API_URL 
          ? `${process.env.NEXT_PUBLIC_API_URL.replace(/\/$/, '')}/api/:path*` 
          : (process.env.NODE_ENV === 'production'
              ? 'https://trapeye-api.onrender.com/api/:path*'
              : 'http://localhost:8000/api/:path*')
      }
    ]
  }
}

export default nextConfig
