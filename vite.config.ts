import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";
import { loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  return {
    define: {
      "import.meta.env.VITE_BACKEND": JSON.stringify("django"),
    },
    server: {
      port: 3000,
      strictPort: true,
      proxy: {
        "/api": env.API_PROXY_TARGET || "http://127.0.0.1:8000",
        "/media": env.API_PROXY_TARGET || "http://127.0.0.1:8000",
      },
    },
    preview: {
      port: 3000,
      strictPort: true,
      proxy: {
        "/api": env.API_PROXY_TARGET || "http://127.0.0.1:8000",
        "/media": env.API_PROXY_TARGET || "http://127.0.0.1:8000",
      },
    },
    build: {
      rollupOptions: {
        output: {
          entryFileNames: "assets/app-[hash].js",
          chunkFileNames: "assets/chunks/[name]-[hash].js",
          manualChunks: {
            "vendor-react": ["react", "react-dom", "react-router-dom"],
            "vendor-query": ["@tanstack/react-query"],
            "vendor-icons": ["lucide-react"],
            "vendor-motion": ["framer-motion", "motion"],
            "vendor-gsap": ["gsap"],
            "vendor-charts": ["recharts"],
            "vendor-pdf": ["pdf-lib", "@pdf-lib/fontkit"],
          },
        },
      },
    },
    plugins: [
      react(),
      VitePWA({
        registerType: "autoUpdate",
        includeAssets: [
          "chapelflow-mark.svg",
          "chapelflow-brand.jpg",
          "chrisland-university-chapel.png",
        ],
        manifest: {
          name: "ChapelFlow",
          short_name: "ChapelFlow",
          description:
            "Digital chapel management for Chrisland University Chapel",
          theme_color: "#4d277b",
          background_color: "#f8f6f2",
          display: "standalone",
          start_url: "/app",
          icons: [
            {
              src: "/chapelflow-mark.svg",
              sizes: "any",
              type: "image/svg+xml",
              purpose: "any maskable",
            },
          ],
        },
        workbox: {
          importScripts: ["/chapelflow-push.js"],
          clientsClaim: true,
          skipWaiting: true,
          navigateFallback: "/index.html",
          navigateFallbackDenylist: [/^\/api\//],
          // Keep the install-time precache to the app shell and shared core chunks.
          // Route feature chunks are cached the first time a student opens that feature.
          globPatterns: [
            "**/*.{html,ico,svg,woff2}",
            "assets/**/*.css",
            "assets/app-*.js",
            "assets/chunks/vendor-react-*.js",
            "assets/chunks/vendor-query-*.js",
            "assets/chunks/vendor-icons-*.js",
          ],
          runtimeCaching: [
            {
              urlPattern: ({ request, url }) =>
                request.destination === "script" &&
                url.origin === (globalThis as unknown as { location: { origin: string } }).location.origin &&
                url.pathname.startsWith("/assets/chunks/"),
              handler: "CacheFirst",
              options: {
                cacheName: "chapelflow-route-chunks-v1",
                expiration: {
                  maxEntries: 120,
                  maxAgeSeconds: 60 * 60 * 24 * 30,
                },
                plugins: [
                  {
                    // Vercel's SPA fallback can return index.html with HTTP 200
                    // for an old/missing chunk URL. Never cache HTML as JavaScript.
                    cacheWillUpdate: async ({ response }) => {
                      const contentType = response.headers.get("content-type") ?? "";
                      return response.ok && /(?:java|ecma)script/i.test(contentType)
                        ? response
                        : null;
                    },
                  },
                ],
              },
            },
            {
              urlPattern: ({ request, url }) =>
                request.destination === "image" &&
                url.origin === (globalThis as unknown as { location: { origin: string } }).location.origin &&
                /^\/(?:chapel-|chapelflow-|chrisland-|chaplain(?:\.|-)|student-chaplain\.)[^/]*\.(?:jpe?g|png|svg|webp)$/.test(url.pathname),
              handler: "CacheFirst",
              options: {
                cacheName: "chapelflow-images-v2",
                expiration: {
                  maxEntries: 40,
                  maxAgeSeconds: 60 * 60 * 24 * 30,
                },
                cacheableResponse: { statuses: [0, 200] },
              },
            },
          ],
        },
      }),
    ],
    test: {
      environment: "jsdom",
      setupFiles: "./src/test/setup.ts",
      css: true,
      include: ["src/**/*.test.{ts,tsx}"],
    },
  };
});
