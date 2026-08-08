/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Needed for `next dev` inside Docker with a bind mount: the container
  // filesystem does not deliver inotify events to the host reliably.
  webpack: (config) => {
    config.watchOptions = { poll: 1000, aggregateTimeout: 300 };
    return config;
  },
};

export default nextConfig;
