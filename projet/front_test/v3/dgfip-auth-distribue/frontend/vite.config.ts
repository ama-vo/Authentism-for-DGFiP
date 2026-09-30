import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
  build: {
    // Pas de source maps embarquées dans les artefacts livrés : le
    // code source TypeScript original ne doit pas être reconstructible
    // depuis l'inspecteur du navigateur en production.
    sourcemap: false,
    minify: "esbuild",
  },
});
