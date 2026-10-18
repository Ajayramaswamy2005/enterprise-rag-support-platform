import { withBotId } from "botid/next/config";
import type { NextConfig } from "next";

const basePath = process.env.IS_DEMO === "1" ? "/demo" : "";

const nextConfig: NextConfig = {
  ...(basePath
    ? {
        assetPrefix: "/demo-assets",
        basePath,
        redirects: async () => [
          {
            basePath: false,
            destination: basePath,
            permanent: false,
            source: "/",
          },
        ],
      }
    : {}),
  cacheComponents: true,
  devIndicators: false,
  env: {
    NEXT_PUBLIC_BASE_PATH: basePath,
    // Shows the Google button only when Google OAuth is configured
    NEXT_PUBLIC_GOOGLE_AUTH_ENABLED:
      (process.env.AUTH_GOOGLE_ID || process.env.GOOGLE_CLIENT_ID) &&
      (process.env.AUTH_GOOGLE_SECRET || process.env.GOOGLE_CLIENT_SECRET)
        ? "1"
        : "",
  },
  experimental: {
    appNewScrollHandler: true,
    cachedNavigations: true,
    inlineCss: true,
    prefetchInlining: true,
    turbopackFileSystemCacheForDev: true,
  },
  images: {
    remotePatterns: [
      {
        hostname: "avatar.vercel.sh",
      },
      {
        hostname: "*.public.blob.vercel-storage.com",
        protocol: "https",
      },
    ],
  },
  logging: {
    fetches: {
      fullUrl: false,
    },
    incomingRequests: false,
  },
  poweredByHeader: false,
  reactCompiler: true,
};

export default withBotId(nextConfig);
