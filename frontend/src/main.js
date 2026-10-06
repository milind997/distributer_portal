import { createApp } from "vue";
import { createRouter, createWebHistory } from "vue-router";
import App from "./App.vue";
import "./style.css";
const router = createRouter({
	history: createWebHistory("/distributor"),
	routes: [{ path: "/:view?", component: { template: "<div/>" } }],
});
createApp(App).use(router).mount("#app");
