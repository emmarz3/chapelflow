import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";
import { loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  return {
    define: {
      "import.meta.env.VITE_BACKEND": JSON.stringify(
        env.VITE_BACKEND || (mode === "test" ? "typescript" : "django"),
      ),
    },
    server: {
      port: 5173,
      strictPort: true,
      proxy: {
        "/api": env.API_PROXY_TARGET || "http://127.0.0.1:8000",
      },
    },
    build: {
      rollupOptions: {
        output: {
          manualChunks: {
            "vendor-react": ["react", "react-dom", "react-router-dom"],
            "vendor-ui": ["framer-motion", "lucide-react"],
            "vendor-data": [
              "@tanstack/react-query",
              "date-fns",
              "react-hook-form",
              "zod",
            ],
            "vendor-charts": ["recharts"],
          },
        },
      },
    },
    plugins: [
      react(),
      VitePWA({
        registerType: "prompt",
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
          navigateFallback: "/index.html",
          runtimeCaching: [
            {
              urlPattern: ({ request }) => request.destination === "image",
              handler: "CacheFirst",
              options: {
                cacheName: "chapelflow-images",
                expiration: {
                  maxEntries: 40,
                  maxAgeSeconds: 60 * 60 * 24 * 30,
                },
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
      include: ["src/**/*.test.{ts,tsx}", "server/**/*.test.ts"],
    },
  };
});
