import { test, expect } from "@playwright/test";

test.describe("Operator Dashboard", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/operator/");
  });

  test("loads with correct title", async ({ page }) => {
    await expect(page).toHaveTitle("ARBITER — Operator Dashboard");
  });

  test("WebSocket connects and shows idle state", async ({ page }) => {
    // Connection indicator is a dot with title="Connected"
    await expect(page.locator("[title='Connected']")).toBeVisible({ timeout: 10_000 });
    // STANDBY appears in both header and vitals — scope to header
    await expect(page.getByRole("banner").getByText("STANDBY")).toBeVisible();
  });

  test("health panel renders service entries", async ({ page }) => {
    const healthPanel = page.getByRole("heading", { name: "SYSTEM HEALTH" }).locator("..");
    await expect(healthPanel).toBeVisible();
    await expect(page.getByText("display server")).toBeVisible();
    // "ONLINE" may appear for multiple services — just verify at least one
    await expect(page.getByText("ONLINE").first()).toBeVisible();
  });

  test("neural feed shows awaiting message", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "NEURAL FEED" })).toBeVisible();
    await expect(page.getByText("Awaiting neural activity...")).toBeVisible();
  });

  test("vitals panel shows initial counters", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "VITALS" })).toBeVisible();
    await expect(page.getByText("Frames")).toBeVisible();
    await expect(page.getByText("Shield")).toBeVisible();
    await expect(page.getByText("100%")).toBeVisible();
  });

  test("score panel shows awaiting judgment", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "SCORE" })).toBeVisible();
    await expect(page.getByText("Awaiting judgment...")).toBeVisible();
  });

  test("command bar has team input, track selector, and disabled START", async ({ page }) => {
    await expect(page.getByPlaceholder("Team name...")).toBeVisible();
    const trackSelect = page.locator("select");
    await expect(trackSelect).toBeVisible();
    const startBtn = page.getByRole("button", { name: "START" });
    await expect(startBtn).toBeVisible();
    await expect(startBtn).toBeDisabled();
  });

  test("START enables when team name is entered", async ({ page }) => {
    await page.getByPlaceholder("Team name...").fill("TestTeam");
    const startBtn = page.getByRole("button", { name: "START" });
    await expect(startBtn).toBeEnabled();
  });

  test("track selector has four options", async ({ page }) => {
    const options = page.locator("select option");
    await expect(options).toHaveCount(4);
    await expect(options.nth(0)).toHaveText("SHADOW::VECTOR");
    await expect(options.nth(1)).toHaveText("SENTINEL::MESH");
    await expect(options.nth(2)).toHaveText("ZERO::PROOF");
    await expect(options.nth(3)).toHaveText("ROGUE::AGENT");
  });

  test("API: /api/health returns status and services", async ({ page }) => {
    const res = await page.evaluate(() =>
      fetch("/api/health").then((r) => r.json()),
    );
    expect(res).toHaveProperty("status");
    expect(res).toHaveProperty("services");
    expect(res.services).toHaveProperty("display_server");
  });

  test("API: /api/metrics returns counters and timers", async ({ page }) => {
    const res = await page.evaluate(() =>
      fetch("/api/metrics").then((r) => r.json()),
    );
    expect(res).toHaveProperty("counters");
    expect(res).toHaveProperty("timers");
  });

  test("API: /api/report-cards returns array", async ({ page }) => {
    const res = await page.evaluate(() =>
      fetch("/api/report-cards").then((r) => r.json()),
    );
    expect(Array.isArray(res)).toBe(true);
  });

  test("demo lifecycle: start → capturing → stop → judging → reset → idle", async ({ page }) => {
    // Wait for WebSocket connection (indicator dot has title="Connected")
    await expect(page.locator("[title='Connected']")).toBeVisible({ timeout: 10_000 });

    // Enter team name and start demo
    // Note: force:true bypasses framer-motion animation stability checks
    await page.getByPlaceholder("Team name...").fill("E2E_Lifecycle");
    const startBtn = page.getByRole("button", { name: "START" });
    await expect(startBtn).toBeEnabled();
    await startBtn.click({ force: true });

    // Verify capturing state (scoped to header to avoid duplicate matches)
    await expect(page.getByRole("banner").getByText("CAPTURING")).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText("E2E_Lifecycle / ROGUE::AGENT")).toBeVisible();

    // Verify STOP and PAUSE buttons appear
    await expect(page.getByRole("button", { name: "STOP" })).toBeVisible();
    await expect(page.getByRole("button", { name: "PAUSE" })).toBeVisible();

    // Wait a moment for frames to accumulate, then stop
    await page.waitForTimeout(3_000);
    await page.getByRole("button", { name: "STOP" }).click({ force: true });

    // Verify stopped/judging state (scoped to header)
    await expect(page.getByRole("banner").getByText("JUDGING")).toBeVisible({ timeout: 10_000 });

    // Wait for final score to appear (format: X.X/10)
    // Score appears in both Neural Feed and Score panel, use first match
    await expect(page.getByText(/\d+\.\d+\s*\/10/).first()).toBeVisible({ timeout: 60_000 });

    // Verify post-stop buttons appear
    const nextBtn = page.getByRole("button", { name: "NEXT TEAM" });
    await expect(nextBtn).toBeVisible();

    // Reset via NEXT TEAM
    await nextBtn.click({ force: true });

    // Verify idle state restored (scoped to header)
    await expect(page.getByRole("banner").getByText("STANDBY")).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText("Awaiting judgment...")).toBeVisible();
    await expect(page.getByPlaceholder("Team name...")).toBeVisible();
  });
});
