import { chromium, expect } from "@playwright/test";
import fs from "node:fs";
const work =
  process.env.DP_TEST_WORKDIR || new URL("../test-results/", import.meta.url).pathname;
const fixture = JSON.parse(
  fs.readFileSync(work + "/browser-fixtures.json", "utf8"),
);
const base = "http://distributor-portal-test.localhost:8001";
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1440, height: 1000 },
});
const page = await context.newPage();
const errors = [];
const completed = [];
page.on("pageerror", (e) => errors.push(e.message));
async function login(p, user, password) {
  await p.goto(base + "/login");
  const status = await p.evaluate(
    async ({ user, password }) =>
      (
        await fetch("/api/method/login", {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: new URLSearchParams({ usr: user, pwd: password }),
        })
      ).status,
    { user, password },
  );
  if (status !== 200) throw new Error("Login failed: " + status);
}
async function navigate(view) {
  await page.goto(base + "/distributor/" + view);
  await page.getByLabel("Select distributor").selectOption(fixture.partner);
  await page.waitForFunction(() => !document.querySelector(".loading"));
}
async function noError(p = page) {
  await expect(p.locator("[role=alert]")).toHaveCount(0);
}
async function addSerial(p, serial) {
  await p.getByLabel("Reel serial number", { exact: true }).fill(serial);
  await p.getByRole("button", { name: "Add", exact: true }).click();
  await expect(p.locator(".scanned-row")).toHaveCount(1);
}
try {
  await login(
    page,
    "Administrator",
    fs.readFileSync(work + "/test-admin-password", "utf8"),
  );
  await navigate("sales");
  await page.getByRole("button", { name: "Record sale", exact: true }).click();
  await page.getByLabel("Buyer / outlet").selectOption(fixture.outlet);
  await page.getByLabel("Your bill number").fill("DP-E2E-SALE");
  await addSerial(page, fixture.serials[0]);
  await page.getByRole("button", { name: "Save sale", exact: true }).click();
  await expect(page.locator(".modal")).toHaveCount(0);
  await noError();
  await expect(page.getByText("DP-E2E-SALE", { exact: true })).toBeVisible();
  completed.push("HQ records a scanned sale");
  await navigate("orders");
  await page.getByRole("button", { name: "Place order", exact: true }).click();
  await page.getByLabel("Quantity " + fixture.item, { exact: true }).fill("2");
  await page.getByRole("button", { name: "Submit for approval" }).click();
  await expect(page.locator(".modal")).toHaveCount(0);
  await noError();
  await page.locator("tbody tr").first().click();
  await page
    .getByRole("button", { name: "Approve & create Sales Order" })
    .click();
  await expect(page.locator(".drawer")).toHaveCount(0);
  await noError();
  await expect(page.getByText("Approved", { exact: true })).toBeVisible();
  completed.push("Order submission and HQ approval create a Sales Order");
  await navigate("returns");
  await page.getByRole("button", { name: "New return" }).click();
  await page
    .getByLabel("Reason", { exact: true })
    .selectOption("Manufacturing defect");
  await page.getByLabel("What happened?").fill("Test reel inspection");
  await addSerial(page, fixture.serials[1]);
  await page.getByRole("button", { name: "Save return" }).click();
  await expect(page.locator(".modal")).toHaveCount(0);
  await noError();
  for (const action of [
    "Mark received at HQ",
    "Mark inspected",
    "Save per-reel decisions",
  ]) {
    await page.locator("tbody tr").first().click();
    await page.getByRole("button", { name: action, exact: true }).click();
    await expect(page.locator(".drawer")).toHaveCount(0);
    await noError();
  }
  completed.push(
    "Return submission, receipt, inspection and per-reel approval",
  );
  await navigate("outlets");
  await page.getByRole("button", { name: "Add outlet", exact: true }).click();
  await page
    .getByLabel("Outlet name", { exact: true })
    .fill("E2E Dealer " + Date.now());
  await page
    .getByLabel("Territory", { exact: true })
    .selectOption(fixture.territory);
  await page.getByRole("button", { name: "Save record" }).click();
  await expect(page.locator(".modal")).toHaveCount(0);
  await page.locator("tbody tr").first().click();
  await page.getByRole("button", { name: "Approve outlet" }).click();
  await expect(page.locator(".drawer")).toHaveCount(0);
  await noError();
  completed.push("New outlet approved by HQ");
  await navigate("forecast");
  await page.getByRole("button", { name: "Generate forecast" }).click();
  await expect(page.locator(".drawer")).toBeVisible();
  await page
    .getByRole("button", { name: "Create order from suggestion" })
    .click();
  await expect(page.locator(".modal")).toBeVisible();
  await noError();
  await page.getByRole("button", { name: "Close dialog" }).click();
  completed.push("Forecast generation and suggested order handoff");
  await navigate("dashboard");
  await page.screenshot({
    path: work + "/populated-dashboard.png",
    fullPage: true,
  });
  const pc = await browser.newContext({
    viewport: { width: 390, height: 844 },
  });
  const partnerPage = await pc.newPage();
  partnerPage.on("pageerror", (e) => errors.push(e.message));
  await login(partnerPage, fixture.user, fixture.password);
  await partnerPage.goto(base + "/distributor/sales");
  await partnerPage
    .getByRole("heading", { name: "Record sales", exact: true })
    .waitFor();
  await partnerPage
    .getByRole("button", { name: "Record sale", exact: true })
    .click();
  await partnerPage.getByLabel("Buyer / outlet").selectOption(fixture.outlet);
  await addSerial(partnerPage, fixture.serials[2]);
  await partnerPage.getByRole("button", { name: "Save sale" }).click();
  await expect(partnerPage.locator(".modal")).toHaveCount(0);
  await noError(partnerPage);
  completed.push("Distributor website user records sale on mobile");
  const scope = await partnerPage.evaluate(async () => {
    const r = await fetch(
      "/api/method/distributor_portal.api.listing?view=stock",
    );
    return r.status;
  });
  expect(scope).toBe(403);
  completed.push("HTTP request without distributor scope denied");
  await partnerPage.screenshot({
    path: work + "/populated-mobile-sales.png",
    fullPage: true,
  });
  await pc.close();
} catch (e) {
  errors.push(e.message);
  await page.screenshot({
    path: work + "/workflow-failure.png",
    fullPage: true,
  });
}
console.log(JSON.stringify({ completed, errors }, null, 2));
await browser.close();
if (errors.length) process.exitCode = 1;
