import { test, expect } from "@playwright/test";

const cards = (page) => page.locator(".wallpaper-grid .wallpaper-card");

// Only the original Pexels artwork is mocked. Added wallpapers are served and
// decoded from the real files in public/wallpapers/kde.
test.beforeEach(async ({ page }) => {
  await page.route("https://images.pexels.com/**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "image/svg+xml",
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="627"><rect width="1200" height="627" fill="#355a67"/></svg>',
      headers: { "access-control-allow-origin": "*" },
    }),
  );
  await page.goto("/");
});

test("homepage presents 56 records with editorial sections and no invented popularity", async ({
  page,
}) => {
  await expect(
    page.getByRole("heading", { name: "Discover wallpapers" }),
  ).toBeVisible();
  await expect(cards(page)).toHaveCount(56);
  await expect(
    page.getByRole("heading", { name: "New to the library", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Collections", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "By category", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: /trending|popular|most liked/i }),
  ).toHaveCount(0);
  await expect(page.locator(".new-section .wallpaper-card")).toHaveCount(4);
  await expect(page.locator(".collection-card")).toHaveCount(4);
  await page.getByRole("button", { name: "View all 32" }).click();
  await expect(cards(page)).toHaveCount(32);
  await expect(
    page.getByRole("heading", { name: "New to the library", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: /Reset filters/ }).click();
  await expect(cards(page)).toHaveCount(56);
});

test("curated collections filter the real catalog and can be cleared", async ({
  page,
}) => {
  const expectations = [
    ["Quiet minimal", 9],
    ["Coastlines", 5],
    ["After dark", 7],
    ["Illustrated worlds", 7],
  ];
  for (const [name, count] of expectations) {
    await page.getByRole("button", { name: `Open collection ${name}` }).click();
    await expect(
      page.getByRole("heading", { name, exact: true }),
    ).toBeVisible();
    await expect(cards(page)).toHaveCount(count);
    await expect(
      page
        .getByRole("group", { name: "Filter by category" })
        .getByRole("button", { name: /^All wallpapers/ }),
    ).toContainText(String(count));
    if (name !== "Illustrated worlds") await page.goto("/");
  }
  await page.goto("/");
  await page
    .getByRole("button", { name: "Open collection Quiet minimal" })
    .click();
  await page.getByRole("button", { name: /Reset filters/ }).click();
  await expect(cards(page)).toHaveCount(56);
});

test("all 32 added wallpapers decode from their real local files", async ({
  page,
}) => {
  test.setTimeout(90_000);
  await page.getByRole("button", { name: "View all 32" }).click();
  const added = cards(page);
  await expect(added).toHaveCount(32);
  for (let index = 0; index < 32; index++) {
    const card = added.nth(index);
    await card.scrollIntoViewIfNeeded();
    await expect(card.locator(".wallpaper-image")).toHaveClass(/image-loaded/);
    const natural = await card.locator("img").evaluate((image) => ({
      width: image.naturalWidth,
      height: image.naturalHeight,
      complete: image.complete,
    }));
    expect(natural.complete).toBe(true);
    expect(natural.width).toBeGreaterThan(1000);
    expect(natural.height).toBeGreaterThan(1000);
  }
  await expect(page.locator(".wallpaper-grid .image-fallback")).toHaveCount(0);
  await expect(cards(page).first().locator(".card-meta")).toContainText(
    "Alesya Khoteeva",
  );
  await expect(cards(page).first().locator(".card-meta")).toContainText(
    "CC BY-SA 4.0",
  );
});

test("added wallpaper detail shows provenance and downloads a real file", async ({
  page,
}) => {
  const filter = page.getByRole("group", { name: "Filter by category" });
  await filter.getByRole("button", { name: /^Nature/ }).click();
  await expect(cards(page)).toHaveCount(9);
  await page
    .getByRole("button", { name: "View details for Altai", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await expect(
    dialog.getByRole("heading", { name: "Altai", exact: true }),
  ).toBeVisible();
  await expect(dialog.locator(".provenance")).toContainText("Alesya Khoteeva");
  await expect(dialog.locator(".provenance")).toContainText("CC BY-SA 4.0");
  await expect(
    dialog.getByRole("link", { name: "Original artwork" }),
  ).toHaveAttribute(
    "href",
    /github\.com\/KDE\/plasma-workspace-wallpapers\/blob\/3e4537eb3852a1c769f6fa003e74d06260c266fb\/Altai\/contents\/images\/5120x2880\.png/,
  );
  await expect(
    dialog.getByRole("link", { name: "License text" }),
  ).toHaveAttribute("href", "/licenses/CC-BY-SA-4.0.txt");
  const image = dialog.getByRole("img", { name: "Altai", exact: true });
  await expect(image).toBeVisible();
  expect(
    await image.evaluate((element) => element.naturalWidth),
  ).toBeGreaterThan(1000);
  await page.keyboard.press("Escape");
  const downloadEvent = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Download Altai", exact: true })
    .click();
  const download = await downloadEvent;
  expect(download.suggestedFilename()).toBe("altai.jpg");
  expect(await download.failure()).toBeNull();
  await expect(page.getByText("Download started: Altai.")).toBeVisible();
});

test("new imagery and glass controls hold at a narrow theme-switched viewport", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  for (const theme of ["light", "dark"]) {
    await page.evaluate(
      (value) => localStorage.setItem("bwe:theme", JSON.stringify(value)),
      theme,
    );
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.getByRole("button", { name: "View all 32" }).click();
    const card = cards(page).first();
    await card.scrollIntoViewIfNeeded();
    await expect(card.locator(".wallpaper-image")).toHaveClass(/image-loaded/);
    await expect(
      card.getByRole("button", { name: "View details for Altai", exact: true }),
    ).toBeVisible();
    await expect(
      card.getByRole("button", { name: "Download Altai", exact: true }),
    ).toBeVisible();
    expect(
      await card.evaluate((element) => {
        const cardRect = element.getBoundingClientRect();
        return [...element.querySelectorAll(".card-controls button")].every(
          (button) => {
            const rect = button.getBoundingClientRect();
            return (
              rect.left >= cardRect.left &&
              rect.right <= cardRect.right &&
              rect.bottom <= cardRect.bottom
            );
          },
        );
      }),
    ).toBe(true);
    await page.goto("/");
  }
});
