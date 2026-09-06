/** @type {import('next').NextConfig} */
export default {
  eslint: { ignoreDuringBuilds: true },

  // In production Vercel routes /api/py/* to the Python function (vercel.json).
  // Locally there is no Vercel, so proxy the same path to `recast serve` instead
  // — that keeps the client code identical in both environments.
  async rewrites() {
    if (process.env.NODE_ENV !== "development") return [];
    const target = process.env.RECAST_API ?? "http://127.0.0.1:8000";
    return [{ source: "/api/py/:path*", destination: `${target}/:path*` }];
  },
};
