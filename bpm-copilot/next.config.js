/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  experimental: {
    serverActions: {
      bodySizeLimit: "5mb", // transcripciones largas
    },
  },
};

module.exports = nextConfig;
