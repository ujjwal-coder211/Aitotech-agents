/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // container deploy (Railway/Docker) के लिए छोटा self-contained server बनाता है
  output: "standalone",
};

export default nextConfig;
