import { test, expect, type Page, type BrowserContext } from "@playwright/test";

/**
 * Operator helper: force-clicks bypass framer-motion animation instability.
 * We verify button state with expect() before force-clicking.
 */
async function operatorStart(
  opPage: Page,
  teamName: string,
  track?: string,
): Promise<void> {
  const input = opPage.getByPlaceholder("Team name...");
  await input.fill(teamName);
  if (track) {
    await opPage.locator("select").selectOption(track);
  }
  const btn = opPage.getByRole("button", { name: "START" });
  await expect(btn).toBeEnabled();
  await btn.click({ force: true });
  await expect(opPage.getByRole("banner").getByText("CAPTURING")).toBeVisible({
    timeout: 5_000,
  });
}

async function operatorStop(opPage: Page): Promise<void> {
  const btn = opPage.getByRole("button", { name: "STOP" });
  await expect(btn).toBeVisible();
  await btn.click({ force: true });
  await expect(opPage.getByRole("banner").getByText("JUDGING")).toBeVisible({
    timeout: 5_000,
  });
}

async function operatorReset(opPage: Page): Promise<void> {
  const btn = opPage.getByRole("button", { name: "NEXT TEAM" });
  await expect(btn).toBeVisible();
  await btn.click({ force: true });
  await expect(opPage.getByRole("banner").getByText("STANDBY")).toBeVisible({
    timeout: 5_000,
  });
}

test.describe("Full Demo Cycle (cross-frontend)", () => {
  let context: BrowserContext;
  let operatorPage: Page;
  let audiencePage: Page;

  test.beforeAll(async ({ browser }) => {
    context = await browser.newContext();
    operatorPage = await context.newPage();
    audiencePage = await context.newPage();

    await operatorPage.goto("http://localhost:8080/operator/");
    await audiencePage.goto("http://localhost:8080/app/");

    // Wait for both WebSocket connections (dot with title="Connected")
    await expect(operatorPage.locator("[title='Connected']")).toBeVisible({
      timeout: 10_000,
    });
    await expect(audiencePage.locator("[title='Connected']")).toBeVisible({
      timeout: 10_000,
    });
  });

  test.afterAll(async () => {
    await context.close();
  });

  test("operator start → audience thinking screen", async () => {
    await operatorStart(operatorPage, "E2E_CrossTest", "SHADOW::VECTOR");

    // Audience should transition to thinking screen
    await expect(
      audiencePage.getByText("ARBITER IS ANALYZING..."),
    ).toBeVisible({ timeout: 10_000 });
    await expect(audiencePage.getByText("E2E_CrossTest")).toBeVisible();
    await expect(audiencePage.getByText("SHADOW::VECTOR")).toBeVisible();
  });

  test("operator stop → audience transitions to commentary or scorecard", async () => {
    await operatorPage.waitForTimeout(3_000);
    await operatorStop(operatorPage);

    // Operator should show JUDGING state
    await expect(operatorPage.getByRole("banner").getByText("JUDGING")).toBeVisible();

    // Audience should show the team name on commentary or scorecard screen
    await expect(
      audiencePage.getByRole("heading", { name: "E2E_CrossTest" })
        .or(audiencePage.getByText("Total Score"))
        .or(audiencePage.getByText("Leaderboard")),
    ).toBeVisible({ timeout: 60_000 });
  });

  test("operator reset → audience returns to idle or leaderboard", async () => {
    // Wait for scoring pipeline to finish
    await expect(
      operatorPage.getByRole("button", { name: "NEXT TEAM" }),
    ).toBeVisible({ timeout: 60_000 });

    await operatorReset(operatorPage);

    // Operator returns to idle
    await expect(operatorPage.getByRole("banner").getByText("STANDBY")).toBeVisible();

    // Audience should show leaderboard or idle screen
    await expect(
      audiencePage.getByText("Leaderboard").or(audiencePage.getByText(/Awaiting next demo/)),
    ).toBeVisible({ timeout: 15_000 });
  });
});
