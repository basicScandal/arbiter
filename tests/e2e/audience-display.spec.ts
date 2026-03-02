import { test, expect } from "@playwright/test";

test.describe("Audience Display", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/app/");
  });

  test("loads with correct title", async ({ page }) => {
    await expect(page).toHaveTitle("ARBITER — Audience Display");
  });

  test("WebSocket connects and shows connected indicator", async ({ page }) => {
    await expect(page.locator("[title='Connected']")).toBeVisible({
      timeout: 10_000,
    });
  });

  test("shows ARBITER heading", async ({ page }) => {
    await expect(
      page.getByRole("heading", { name: "ARBITER" }),
    ).toBeVisible();
  });

  test("shows footer branding", async ({ page }) => {
    await expect(
      page.getByText("NEBULA:FOG 2026 — AI-Powered Judging"),
    ).toBeVisible();
  });

  test("idle state shows awaiting message", async ({ page }) => {
    await expect(
      page.getByText(/Awaiting next demo/),
    ).toBeVisible({ timeout: 10_000 });
  });
});
