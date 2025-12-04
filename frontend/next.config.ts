import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  reactCompiler: true,
  allowedDevOrigins: ['http://192.168.50.169:3000', '192.168.50.169'],
};

export default nextConfig;
