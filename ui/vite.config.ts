/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Built into the Python package, where the window loads it from disk, so
// asset paths must be relative ("./") rather than rooted at a server.
export default defineConfig({
  plugins: [react()],
  base: "./",
  build: {
    outDir: "../highlights/app/web",
    emptyOutDir: true,
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
  },
});
