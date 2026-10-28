import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

// Test-only imagery: never imported by the application or added to its catalog.
const fixture =
  '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="627"><rect width="1200" height="627" fill="#507784"/><circle cx="900" cy="180" r="120" fill="#e5d6b1"/><path d="M0 627V400L400 150l450 477Z" fill="#294957"/></svg>';

test.beforeEach(async ({ page }) => {
  await page.route("https://images.pexels.com/**", (route) =>
    route.fulfill({
      contentType: "image/svg+xml",
      body: fixture,
      headers: { "access-control-allow-origin": "*" },
    }),
  );
  await page.goto("/");
});

test("image-filled glass cards contain every control at all requested widths and themes", async ({
  page,
}) => {
  for (const width of [1440, 1280, 1024, 768, 430, 390, 375]) {
    await page.setViewportSize({ width, height: 900 });
    for (const theme of ["light", "dark"]) {
      await page.evaluate(
        (value) => localStorage.setItem("bwe:theme", JSON.stringify(value)),
        theme,
      );
      await page.reload();
      const card = page.locator(".wallpaper-grid .wallpaper-card").first();
      await card.scrollIntoViewIfNeeded();
      await expect(card.locator(".wallpaper-image")).toHaveClass(
        /image-loaded/,
      );
      await expect(card.locator(".card-footer")).toHaveCount(0);
      await expect(card).toHaveCSS("border-radius", "24px");
      await expect(card.locator(".wallpaper-actions")).toHaveCSS(
        "backdrop-filter",
        "blur(14px)",
      );
      const geometry = await card.evaluate((element) => {
        const cardRect = element.getBoundingClientRect();
        const imageRect = element.querySelector("img").getBoundingClientRect();
        const panel = element.querySelector(".card-overlay");
        return {
          overflow: document.documentElement.scrollWidth > innerWidth,
          imageWidth: imageRect.width,
          imageHeight: imageRect.height,
          width: cardRect.width,
          height: cardRect.height,
          panelInside: panel.getBoundingClientRect().bottom <= cardRect.bottom,
          gradient: getComputedStyle(panel).backgroundImage,
          controlsInside: [
            ...element.querySelectorAll(".card-controls button"),
          ].every((button) => {
            const rect = button.getBoundingClientRect();
            return (
              rect.width >= 40 &&
              rect.height >= 40 &&
              rect.left >= cardRect.left &&
              rect.right <= cardRect.right &&
              rect.top >= cardRect.top &&
              rect.bottom <= cardRect.bottom
            );
          }),
        };
      });
      expect(geometry.overflow).toBe(false);
      expect(geometry.imageWidth).toBeCloseTo(geometry.width - 2, 0);
      expect(geometry.imageHeight).toBeCloseTo(geometry.height - 2, 0);
      expect(geometry.panelInside).toBe(true);
      expect(geometry.controlsInside).toBe(true);
      expect(geometry.gradient).toContain("linear-gradient");
      for (const name of [
        "Like Seoul Street Art",
        "Save Seoul Street Art",
        "Download Seoul Street Art",
        "View details for Seoul Street Art",
      ]) {
        await expect(
          card.getByRole("button", { name, exact: true }),
        ).toBeVisible();
      }
    }
  }
});

test("integrated View and glass action controls work by keyboard without accidental navigation", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const card = page.locator(".wallpaper-grid .wallpaper-card").first();
  await card
    .getByRole("button", { name: "Like Seoul Street Art", exact: true })
    .focus();
  await page.keyboard.press("Space");
  await expect(
    card.getByRole("button", { name: "Unlike Seoul Street Art" }),
  ).toHaveAttribute("aria-pressed", "true");
  await page.keyboard.press("Tab");
  await page.keyboard.press("Space");
  await expect(
    card.getByRole("button", { name: "Unsave Seoul Street Art" }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  const view = card.getByRole("button", {
    name: "View details for Seoul Street Art",
  });
  await view.focus();
  await page.keyboard.press("Enter");
  await expect(
    page
      .getByRole("dialog")
      .getByRole("heading", { name: "Seoul Street Art", exact: true }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(view).toBeFocused();
});

test("readability survives white imagery, no backdrop blur, and active controls", async ({
  page,
}) => {
  await page.route("https://images.pexels.com/**", (route) =>
    route.fulfill({
      contentType: "image/svg+xml",
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="627"><rect width="1200" height="627" fill="white"/></svg>',
    }),
  );
  await page.reload();
  await page.addStyleTag({
    content:
      ".wallpaper-card * { backdrop-filter: none !important; -webkit-backdrop-filter: none !important; }",
  });
  const card = page.locator(".wallpaper-grid .wallpaper-card").first();
  await card.scrollIntoViewIfNeeded();
  await expect(card.locator(".wallpaper-image")).toHaveClass(/image-loaded/);
  await card
    .getByRole("button", { name: "Like Seoul Street Art", exact: true })
    .click();
  await card
    .getByRole("button", { name: "Save Seoul Street Art", exact: true })
    .click();
  const results = await new AxeBuilder({ page })
    .include(".wallpaper-grid")
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(results.violations).toEqual([]);
  await expect(
    card.getByRole("button", { name: "View details for Seoul Street Art" }),
  ).toBeEnabled();
});

test("glass-card hover respects reduced-motion preference", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  const image = page.locator(".wallpaper-grid .wallpaper-card img").first();
  await page.locator(".wallpaper-grid .wallpaper-card").first().hover();
  await expect(image).toHaveCSS("transform", "none");
  await expect(image).toHaveCSS("transition-duration", "0s");
});
