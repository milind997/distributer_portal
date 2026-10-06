import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
export default defineConfig({
	plugins: [vue()],
	base: "/assets/distributor_portal/frontend/",
	build: { outDir: "../distributor_portal/public/frontend", emptyOutDir: true },
});
