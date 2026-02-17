import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: "/operator/",
  server: {
    proxy: {
      "/ws/operator": {
        target: "ws://localhost:8080",
        ws: true,
      },
    },
  },
});
