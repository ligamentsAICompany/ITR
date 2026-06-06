import type { NextConfig } from "next";
import { resolveBackendInternalUrl } from "./lib/apiRouting";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    const backendUrl = resolveBackendInternalUrl(process.env.BACKEND_INTERNAL_URL);
    return [
      {
        source: "/v1/:path*",
        destination: `${backendUrl}/v1/:path*`,
      },
      {
        source: "/health",
        destination: `${backendUrl}/health`,
      },
    ];
  },
};

export default nextConfig;
