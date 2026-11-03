import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "./",
  build: {
    target: "esnext",
    outDir: "dist",
    assetsInlineLimit: 100000,
  },
  test: {
    environment: "jsdom",
    globals: true,
  },
});
