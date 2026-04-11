/** @type {import('next').NextConfig} */
const nextConfig = {
  // API_URL is read at runtime by the frontend via NEXT_PUBLIC_API_URL.
  // No server-side proxy rewrites are needed since api.ts calls the backend directly.
};

module.exports = nextConfig;
