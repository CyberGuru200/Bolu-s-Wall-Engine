import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

// A deterministic image fixture, only intercepted in tests. Never shipped as catalog imagery.
const imageFixture =
  '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="627"><rect width="1200" height="627" fill="#355a67"/><circle cx="900" cy="180" r="120" fill="#d5c6a1"/><path d="M0 627V400L400 150l450 477Z" fill="#203e47"/></svg>';
const cards = (page) => page.locator(".wallpaper-grid .wallpaper-card");
const filter = (page, name) =>
  page
    .getByRole("group", { name: "Filter by category" })
    .getByRole("button", { name: new RegExp(`^${name}`) });
const navigate = async (page, name) => {
  const menu = page.getByRole("button", {
    name: "Open navigation",
    exact: true,
  });
  if (await menu.isVisible()) await menu.click();
  await page
    .getByRole("navigation", { name: "Main navigation" })
    .getByRole("link", { name: new RegExp(`^${name}`) })
    .click();
};

test.beforeEach(async ({ page }) => {
  await page.route("https://images.pexels.com/**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "image/svg+xml",
      body: imageFixture,
      headers: { "access-control-allow-origin": "*" },
    }),
  );
  await page.goto("/");
});

test("home, image loading, category counts, and sort", async ({ page }) => {
  await expect(
    page.getByRole("heading", { name: "Discover wallpapers" }),
  ).toBeVisible();
  await expect(cards(page)).toHaveCount(56);
  await expect(page.locator(".featured-card")).toHaveCount(3);
  await expect(cards(page).first().locator(".wallpaper-image")).toHaveClass(
    /image-loaded/,
  );
  for (const [category, count] of [
    ["Anime", 6],
    ["Abstract", 21],
    ["Minimalist", 9],
    ["Colored", 6],
    ["Nature", 9],
    ["Space", 2],
    ["Illustration", 3],
  ]) {
    await filter(page, category).click();
    await expect(cards(page)).toHaveCount(count);
    await expect(filter(page, category)).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await expect(cards(page).first().locator(".card-category")).toHaveText(
      category,
    );
  }
  await filter(page, "All wallpapers").click();
  await page.getByLabel("Sort wallpapers").selectOption("title");
  await expect(cards(page).first().locator(".card-title")).toHaveText(
    "Abstract Lines",
  );
});

test("combined search, category, empty state, and reset", async ({ page }) => {
  const search = page.getByRole("searchbox", { name: "Search wallpapers" });
  await search.fill("TOKYO neon");
  await expect(cards(page)).toHaveCount(1);
  await expect(cards(page).first()).toContainText("Tokyo Neon Signs");
  await filter(page, "Abstract").click();
  await expect(cards(page)).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "No wallpapers found" }),
  ).toBeVisible();
  await page
    .locator(".empty-state")
    .getByRole("button", { name: "Reset filters" })
    .click();
  await expect(cards(page)).toHaveCount(56);
  await expect(search).toHaveValue("");
  await search.fill("minimalist");
  await expect(cards(page)).toHaveCount(9);
  await page.getByRole("button", { name: "Clear search" }).click();
  await expect(search).toBeFocused();
  await expect(cards(page)).toHaveCount(56);
});

test("likes, saves, local persistence, and empty library views", async ({
  page,
}) => {
  await page
    .getByRole("button", { name: "Like Seoul Street Art", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Save Seoul Street Art", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Unlike Seoul Street Art" }),
  ).toHaveAttribute("aria-pressed", "true");
  await page.reload();
  await navigate(page, "Liked wallpapers");
  await expect(cards(page)).toHaveCount(1);
  await page.getByRole("searchbox").fill("zzzz");
  await expect(cards(page)).toHaveCount(0);
  await page.getByRole("button", { name: "Clear search" }).click();
  await page.getByRole("button", { name: "Unlike Seoul Street Art" }).click();
  await expect(
    page.getByRole("heading", { name: "Your favorites start here" }),
  ).toBeVisible();
  await navigate(page, "Saved wallpapers");
  await expect(cards(page)).toHaveCount(1);
  await page.getByRole("button", { name: "Unsave Seoul Street Art" }).click();
  await expect(cards(page)).toHaveCount(0);
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Make room for inspiration" }),
  ).toBeVisible();
});

test("detail, actions, related wallpapers, Escape and focus restoration", async ({
  page,
}) => {
  const opener = page.getByRole("button", {
    name: "View Seoul Street Art",
    exact: true,
  });
  await opener.click();
  const dialog = page.getByRole("dialog");
  await expect(
    dialog.getByRole("heading", { name: "Seoul Street Art", exact: true }),
  ).toBeVisible();
  await expect(
    dialog.getByRole("img", { name: "Seoul Street Art" }),
  ).toBeVisible();
  await dialog
    .getByRole("button", { name: "Like Seoul Street Art", exact: true })
    .click();
  await dialog
    .getByRole("button", { name: "Save Seoul Street Art", exact: true })
    .click();
  await expect(
    dialog.getByRole("button", { name: "Unlike Seoul Street Art" }),
  ).toHaveAttribute("aria-pressed", "true");
  await dialog
    .getByRole("button", { name: "View Akihabara Neon Night" })
    .click();
  await expect(
    dialog.getByRole("heading", { name: "Akihabara Neon Night", exact: true }),
  ).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(opener).toBeFocused();
  await expect(
    page.getByRole("button", { name: "Unsave Seoul Street Art" }),
  ).toHaveAttribute("aria-pressed", "true");
});

test("modal contains keyboard focus and closes with its button or backdrop", async ({
  page,
}) => {
  await page
    .getByRole("button", { name: "View Seoul Street Art", exact: true })
    .click();
  for (let index = 0; index < 15; index++) {
    await page.keyboard.press("Tab");
    expect(
      await page.evaluate(() => !!document.activeElement.closest("dialog")),
    ).toBe(true);
  }
  await page.getByRole("button", { name: "Close dialog" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page
    .getByRole("button", { name: "View Seoul Street Art", exact: true })
    .click();
  await page.mouse.click(1, 1);
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("download produces an actual file and announces success", async ({
  page,
}) => {
  const downloadEvent = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Download Seoul Street Art", exact: true })
    .click();
  const download = await downloadEvent;
  expect(download.suggestedFilename()).toBe("seoul-street-art.svg");
  expect(await download.failure()).toBeNull();
  await expect(
    page.getByText("Download started: Seoul Street Art."),
  ).toBeVisible();
});

test("network failure and non-image download response show source fallback", async ({
  page,
}) => {
  await page.route("https://images.pexels.com/**", (route) => route.abort());
  await page
    .getByRole("button", { name: "Download Seoul Street Art", exact: true })
    .click();
  await expect(page.getByText(/Direct download is unavailable/)).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Open source image" }),
  ).toHaveAttribute("href", /32014936/);
  await expect(
    page.getByRole("link", { name: "Open source image" }),
  ).toHaveAttribute("target", "_blank");
  await page.getByRole("button", { name: "Dismiss download message" }).click();
  await page.route("https://images.pexels.com/**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "text/html",
      body: "<html>Error</html>",
      headers: { "access-control-allow-origin": "*" },
    }),
  );
  await page
    .getByRole("button", { name: "View Seoul Street Art", exact: true })
    .click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Download Seoul Street Art" })
    .click();
  await expect(
    page.getByRole("dialog").getByText(/Direct download is unavailable/),
  ).toBeVisible();
});

test("broken images keep details and actions usable", async ({ page }) => {
  await page.route("https://images.pexels.com/**", (route) => route.abort());
  await page.reload();
  await expect(
    cards(page).first().getByText("Preview unavailable"),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "View Seoul Street Art", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await expect(
    dialog.locator(".detail-image").getByText("Preview unavailable"),
  ).toBeVisible();
  await dialog
    .getByRole("button", { name: "Save Seoul Street Art", exact: true })
    .click();
  await expect(
    dialog.getByRole("button", { name: "Unsave Seoul Street Art" }),
  ).toHaveAttribute("aria-pressed", "true");
});

test("both themes persist and use distinct token sets", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "light" });
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.getByRole("button", { name: "Switch to dark theme" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(page.locator("body")).toHaveCSS(
    "background-color",
    "rgb(18, 23, 25)",
  );
  await page.getByRole("button", { name: "Switch to light theme" }).click();
  await expect(page.locator("body")).toHaveCSS(
    "background-color",
    "rgb(248, 249, 251)",
  );
});

test("categories, profile shortcuts, hash links and browser history", async ({
  page,
}) => {
  await navigate(page, "Categories");
  await expect(page.locator(".category-tile")).toHaveCount(7);
  await page.getByRole("button", { name: "Abstract 21 wallpapers" }).click();
  await expect(cards(page)).toHaveCount(21);
  await navigate(page, "Explore");
  await expect(cards(page)).toHaveCount(56);
  await page.goBack();
  await expect(
    page.getByRole("heading", { name: "Browse by category" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Open local profile" }).click();
  await expect(page.getByRole("dialog")).toContainText(
    "not in an online account",
  );
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "0 Saved wallpapers" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Saved wallpapers", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.goto("/#liked");
  await expect(
    page.getByRole("heading", { name: "Liked wallpapers", exact: true }),
  ).toBeVisible();
});

test("corrupt or blocked local storage never crashes the app", async ({
  page,
}) => {
  await page.addInitScript(() => {
    localStorage.setItem("bwe:liked", "{corrupt");
    localStorage.setItem("bwe:saved", JSON.stringify([9999]));
    localStorage.setItem("bwe:theme", JSON.stringify("invalid"));
  });
  await page.reload();
  await expect(cards(page)).toHaveCount(56);
  await expect(
    page.getByText(/Browser storage is unavailable or was reset/),
  ).toBeVisible();
  await page.addInitScript(() => {
    Storage.prototype.setItem = () => {
      throw new Error("Storage blocked");
    };
    Storage.prototype.getItem = () => {
      throw new Error("Storage blocked");
    };
  });
  await page.reload();
  await page
    .getByRole("button", { name: "Like Seoul Street Art", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Unlike Seoul Street Art" }),
  ).toHaveAttribute("aria-pressed", "true");
});

for (const width of [1440, 1280, 1024, 768, 430, 390, 375]) {
  test(`responsive layout and interactions at ${width}px in both themes`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
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
      const columns = await page
        .locator(".wallpaper-grid")
        .evaluate(
          (element) =>
            getComputedStyle(element).gridTemplateColumns.split(" ").length,
        );
      expect(columns).toBe(
        width >= 1400 ? 4 : width > 1150 ? 3 : width > 540 ? 2 : 1,
      );
      await filter(page, "Colored").click();
      await expect(cards(page)).toHaveCount(6);
      await page
        .getByRole("button", { name: "View Rainbow LED Tubes", exact: true })
        .click();
      await expect(
        page
          .getByRole("dialog")
          .getByRole("heading", { name: "Rainbow LED Tubes", exact: true }),
      ).toBeVisible();
      const bounds = await page.getByRole("dialog").boundingBox();
      expect(bounds.x).toBeGreaterThanOrEqual(0);
      expect(bounds.x + bounds.width).toBeLessThanOrEqual(width);
      await page
        .getByRole("dialog")
        .getByRole("button", { name: "Like Rainbow LED Tubes", exact: true })
        .click();
      await page
        .getByRole("dialog")
        .getByRole("button", { name: "Save Rainbow LED Tubes", exact: true })
        .click();
      await page.keyboard.press("Escape");
      await navigate(page, "Liked wallpapers");
      await expect(cards(page)).toHaveCount(1);
      await navigate(page, "Saved wallpapers");
      await expect(cards(page)).toHaveCount(1);
      await page
        .getByRole("button", { name: "Unlike Rainbow LED Tubes" })
        .click();
      await page
        .getByRole("button", { name: "Unsave Rainbow LED Tubes" })
        .click();
      await navigate(page, "Home");
      await expect(
        page.getByRole("heading", { name: "Discover wallpapers" }),
      ).toBeVisible();
    }
  });
}

test("mobile navigation keyboard trap, dismissal, and desktop resize", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const menu = page.getByRole("button", {
    name: "Open navigation",
    exact: true,
  });
  await menu.click();
  await expect(
    page.getByRole("link", { name: "Bolu's Wall Engine home" }),
  ).toBeFocused();
  for (let index = 0; index < 10; index++) {
    await page.keyboard.press("Tab");
    expect(
      await page.evaluate(
        () =>
          !!document.activeElement.closest("#site-navigation, .mobile-menu"),
      ),
    ).toBe(true);
  }
  await page.keyboard.press("Escape");
  await expect(menu).toBeFocused();
  await expect(page.locator("main")).not.toHaveAttribute("inert");
  await menu.click();
  await page.setViewportSize({ width: 1280, height: 900 });
  await expect(page.locator("main")).not.toHaveAttribute("inert");
  await expect(page.locator(".nav-backdrop")).toHaveCount(0);
});

for (const width of [1440, 375]) {
  for (const theme of ["light", "dark"]) {
    test(`automated accessibility audit: ${width}px ${theme}`, async ({
      page,
    }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.evaluate(
        (value) => localStorage.setItem("bwe:theme", JSON.stringify(value)),
        theme,
      );
      await page.reload();
      await expect(
        page.locator(".featured-card").first().locator(".wallpaper-image"),
      ).toHaveClass(/image-loaded/);
      const audit = () =>
        new AxeBuilder({ page })
          .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
          .analyze();
      expect((await audit()).violations).toEqual([]);
      await page
        .getByRole("button", { name: "View Seoul Street Art", exact: true })
        .click();
      expect((await audit()).violations).toEqual([]);
      await page.keyboard.press("Escape");
      await page.getByRole("button", { name: "Open local profile" }).click();
      expect((await audit()).violations).toEqual([]);
    });
  }
}

test("skip link and back to top retain the current collection", async ({
  page,
}) => {
  await navigate(page, "Saved wallpapers");
  const skip = page.getByRole("link", { name: "Skip to wallpapers" });
  await skip.focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("main")).toBeFocused();
  await expect(
    page.getByRole("heading", { name: "Saved wallpapers", exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Back to top" }).click();
  await expect(page).toHaveURL(/#saved$/);
  await expect(page.locator("main")).toBeFocused();
});
