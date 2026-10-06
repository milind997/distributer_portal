import { chromium } from "@playwright/test";
import fs from "node:fs";
const work =
  process.env.DP_TEST_WORKDIR || new URL("../test-results/", import.meta.url).pathname;
const base = "http://test-com.localhost:8001";
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1440, height: 1000 },
});
await context.addCookies([
  {
    name: "sid",
    value: fs.readFileSync(work + "/main-verification-session", "utf8"),
    domain: "test-com.localhost",
    path: "/",
    httpOnly: true,
    sameSite: "Lax",
  },
]);
const page = await context.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
for (const [route, title] of [
  ["dashboard", "Overview"],
  ["orders", "Orders"],
  ["stock", "My stock"],
  ["sales", "Record sales"],
  ["declarations", "Stock declarations"],
  ["returns", "Returns & damage"],
  ["accounts", "Account & credit"],
  ["forecast", "Forecast"],
  ["outlets", "Outlets"],
  ["network", "Network overview"],
  ["flags", "Territory flags"],
  ["partners", "Channel partners"],
  ["settings", "Portal settings"],
]) {
  const response = await page.goto(base + "/distributor/" + route);
  if (response.status() !== 200)
    errors.push(route + ": HTTP " + response.status());
  await page.getByRole("heading", { name: title, exact: true }).waitFor();
  await page.waitForFunction(() => !document.querySelector(".loading"));
  if (await page.locator("[role=alert]").count())
    errors.push(
      route + ": " + (await page.locator("[role=alert]").first().innerText()),
    );
}
await page.goto(base + "/distributor");
await page.waitForSelector(".stats");
await page.screenshot({
  path: work + "/main-portal-desktop.png",
  fullPage: true,
});
await page.goto(base + "/desk");
await page.waitForLoadState("networkidle", { timeout: 20000 }).catch(() => {});
const shortcuts = await page
  .getByText("Open Distributor Portal", { exact: true })
  .count();
const tiles = await page
  .getByText("Distributor Portal", { exact: true })
  .count();
await page.screenshot({ path: work + "/main-desk.png", fullPage: true });
console.log(
  JSON.stringify(
    {
      portalErrors: errors,
      deskShortcutCount: shortcuts,
      deskPortalCount: tiles,
      deskURL: page.url(),
    },
    null,
    2,
  ),
);
if (shortcuts || tiles) {
  const next = context
    .waitForEvent("page", { timeout: 5000 })
    .catch(() => null);
  await page
    .getByText(shortcuts ? "Open Distributor Portal" : "Distributor Portal", {
      exact: true,
    })
    .first()
    .click();
  const opened = await next;
  const target = opened || page;
  await target.waitForURL("**/distributor**");
  await target
    .getByRole("heading", { name: "Overview", exact: true })
    .waitFor();
  console.log("Desk tile opens " + target.url());
  if (opened) await opened.close();
}
await page.goto(base + "/crm/leads/view/list");
await page.waitForTimeout(1200);
await page.screenshot({ path: work + "/crm-reference.png", fullPage: true });
await browser.close();
if (errors.length) process.exitCode = 1;
