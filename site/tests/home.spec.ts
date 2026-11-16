import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { contrastFailures } from "../component-tests/contrast";
import { languages } from "../src/data/languages";
const comparison = JSON.parse(
  readFileSync("src/data/home-comparison.json", "utf8"),
) as {
  verified: string;
  products: string[];
  rows: { cells: { source: { href: string } }[] }[];
};

test("v2 explains local setup and keeps devices, sources, languages and creator credit intact", async ({
  page,
}) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      get() {
        throw new Error("No device access");
      },
    });
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      get() {
        throw new Error("No clipboard access");
      },
    });
  });
  const errors: string[] = [];
  const fonts: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("request", (request) => {
    if (request.resourceType() === "font") fonts.push(request.url());
  });
  await page.goto("./");
  await page.evaluate(() => document.fonts.ready);
  await expect(
    page.getByRole("complementary", { name: "Project announcement" }),
  ).toContainText("Windows preview");
  await expect(page.locator(".how-grid article")).toHaveCount(3);
  await expect(page.locator(".feature-bento article")).toHaveCount(5);
  await expect(page.locator(".command-tile")).toContainText(
    "Experimental, off by default",
  );
  await expect(page.locator(".preview-tile")).toContainText(
    "optional English preview",
  );
  await expect(page.locator(".language-wall > li")).toHaveCount(
    languages.length + 1,
  );
  await expect(page.locator(".language-accuracy")).toContainText(
    "Coverage and measured accuracy are separate",
  );
  await expect(page.locator(".faq-section details")).toHaveCount(10);
  for (const label of await page
    .locator(".small-bar [data-bar-label]:visible")
    .all()) {
    expect(
      await label.evaluate((node) => node.getBoundingClientRect().height),
    ).toBeGreaterThanOrEqual(11);
    expect(
      await label.evaluate((node) =>
        parseFloat(getComputedStyle(node).fontSize),
      ),
    ).toBeGreaterThanOrEqual(11);
  }
  await expect(
    page.getByRole("link", { name: "Verify it offline yourself" }),
  ).toHaveAttribute("href", "/saydraft/docs/privacy/verify-offline/");
  const stars = page.getByRole("link", {
    name: /^\d[\d,]* GitHub stars?\. Checked \d{4}-\d{2}-\d{2}$/,
  });
  await expect(stars).toHaveCount(1);
  await expect(stars).toHaveAttribute(
    "href",
    "https://github.com/tanzir71/saydraft",
  );
  const footer = page.getByRole("contentinfo");
  for (const label of [
    "Product links",
    "Compare dictation tools",
    "Documentation links",
    "Language links",
    "Creator links",
  ])
    await expect(footer.getByRole("navigation", { name: label })).toHaveCount(
      1,
    );
  await expect(
    footer.getByRole("link", { name: "Built by tanziro.com" }),
  ).toHaveAttribute("href", "https://tanziro.com");
  expect(await contrastFailures(page, "body")).toEqual([]);
  // The faded filler remains visible text; opacity must still meet large-text AA.
  const fillerContrast = await page.locator(".filler > span:first-child").evaluate((node) => {
    const rgb = (value: string) => value.match(/[\d.]+/g)!.slice(0, 3).map(Number);
    const style = getComputedStyle(node), ink = rgb(style.color);
    const paper = rgb(getComputedStyle(document.documentElement).backgroundColor);
    const alpha = Number(style.opacity);
    const luminance = (color: number[]) => color.reduce((sum, value, i) => {
      const c = value / 255;
      return sum + (c <= .04045 ? c / 12.92 : ((c + .055) / 1.055) ** 2.4) * [.2126, .7152, .0722][i];
    }, 0);
    return (luminance(paper) + .05) / (luminance(ink.map((c, i) => c * alpha + paper[i] * (1 - alpha))) + .05);
  });
  expect(fillerContrast).toBeGreaterThanOrEqual(3);
  await page.keyboard.press("Tab");
  for (const target of [
    page
      .getByRole("navigation", { name: "Main navigation" })
      .getByRole("link", { name: "Get Saydraft", exact: true }),
    page.locator(".hero-buttons a").last(),
    page.getByRole("link", { name: "Verify it offline yourself" }),
    page.locator('.cleanup-tabs [aria-selected="true"]'),
    page.locator(".more-languages a"),
  ]) {
    await target.focus();
    const ring = await target.evaluate((node) => {
      const style = getComputedStyle(node),
        rect = node.getBoundingClientRect();
      const width = parseFloat(style.outlineWidth),
        offset = parseFloat(style.outlineOffset);
      const point = {
        x: rect.left - offset - width / 2,
        y: rect.top + rect.height / 2,
      };
      let surface = "rgb(255,255,255)";
      for (
        let parent = node.parentElement;
        parent;
        parent = parent.parentElement
      ) {
        const box = parent.getBoundingClientRect(),
          color = getComputedStyle(parent).backgroundColor;
        const rgba = color.match(/[\d.]+/g)?.map(Number) ?? [];
        if (
          (rgba[3] ?? 1) === 1 &&
          rgba.length >= 3 &&
          point.x >= box.left &&
          point.x <= box.right &&
          point.y >= box.top &&
          point.y <= box.bottom
        ) {
          surface = color;
          break;
        }
      }
      const luminance = (color: string) =>
        color
          .match(/[\d.]+/g)!
          .slice(0, 3)
          .map(Number)
          .reduce((sum, value, i) => {
            const c = value / 255;
            return (
              sum +
              (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4) *
                [0.2126, 0.7152, 0.0722][i]
            );
          }, 0);
      const a = luminance(style.outlineColor),
        b = luminance(surface);
      return {
        visible:
          node.matches(":focus-visible") && style.outlineStyle !== "none",
        width,
        offset,
        contrast: (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05),
      };
    });
    expect(ring.visible).toBe(true);
    expect(ring.width).toBeGreaterThanOrEqual(2);
    expect(ring.offset).toBeGreaterThanOrEqual(5);
    expect(ring.contrast).toBeGreaterThanOrEqual(3);
  }
  expect(fonts.some((url) => url.includes("instrument-serif"))).toBe(false);
  expect(errors).toEqual([]);
});

test("comparison sources stay dated and its table scrolls by keyboard within the page", async ({
  page,
}) => {
  await page.goto("./#compare");
  const region = page.getByRole("region", {
    name: "Compare your everyday dictation setup",
  });
  await expect(region).toBeInViewport();
  await expect(region.locator("thead th")).toHaveText([
    "Feature",
    ...comparison.products,
  ]);
  await expect(region.locator("tbody tr")).toHaveCount(3);
  await expect(region.locator("td time")).toHaveCount(12);
  for (const time of await region.locator("time").all())
    await expect(time).toHaveAttribute("datetime", comparison.verified);
  for (const [index, cell] of comparison.rows
    .flatMap((row) => row.cells)
    .entries())
    await expect(
      region.locator("td").nth(index).getByRole("link"),
    ).toHaveAttribute("href", cell.source.href);
  await expect(
    page
      .getByRole("navigation", { name: "Detailed dictation comparisons" })
      .getByRole("link"),
  ).toHaveCount(5);
  await region.focus();
  await expect(region).toBeFocused();
  if (await region.evaluate((node) => node.scrollWidth > node.clientWidth)) {
    await page.keyboard.press("ArrowRight");
    await expect
      .poll(() => region.evaluate((node) => node.scrollLeft))
      .toBeGreaterThan(0);
  }
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});

test("hero simulation progresses with motion and finishes directly with reduced motion", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.goto("./");
  const button = page.getByRole("button", { name: "Play the example" });
  const bar = page.locator("[data-demo-scene] [data-bar-demo]");
  await page.locator("[data-demo-scene]").scrollIntoViewIfNeeded();
  // First-view playback and explicit replay use the same sequence.
  await expect(bar).toHaveAttribute("data-state", "inserted");
  await expect(button).toBeEnabled();
  await button.click();
  await expect(bar).toHaveAttribute("data-state", "listening");
  await expect(button).toBeDisabled();
  await expect(bar).toHaveAttribute("data-state", "cleaning");
  await expect(bar).toHaveAttribute("data-state", "inserted");
  await expect(button).toBeEnabled();
  await button.click();
  await expect(bar).toHaveAttribute("data-state", "listening");
  await page.emulateMedia({ reducedMotion: "reduce" });
  await expect(bar).toHaveAttribute("data-state", "inserted");
  await expect(button).toBeEnabled();
  await button.click();
  await expect(bar).toHaveAttribute("data-state", "inserted", {
    timeout: 1000,
  });
  await expect(page.getByRole("status")).toContainText("Example finished");
});

test("cleanup tabs support keyboard navigation, focus and all five examples", async ({
  page,
}) => {
  await page.goto("./#cleanup");
  const tabs = page.getByRole("tablist", { name: "Cleanup examples" });
  await expect(tabs.getByRole("tab")).toHaveCount(5);
  const horizontal =
    (await tabs.getAttribute("aria-orientation")) === "horizontal";
  await tabs.getByRole("tab", { name: /Change your mind/ }).focus();
  await page.keyboard.press(horizontal ? "ArrowRight" : "ArrowDown");
  await expect(tabs.getByRole("tab", { name: /Drop the ums/ })).toBeFocused();
  await expect(page.getByRole("tabpanel")).toContainText(
    "I think this could work.",
  );
  await page.keyboard.press("End");
  await expect(
    tabs.getByRole("tab", { name: /Match the app/ }),
  ).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("tabpanel")).toContainText(
    "Can you send the notes when you get a chance?",
  );
  await page.keyboard.press("Home");
  await expect(
    tabs.getByRole("tab", { name: /Change your mind/ }),
  ).toBeFocused();
  await tabs.getByRole("tab", { name: /Make a list/ }).click();
  await expect(page.getByRole("tabpanel")).toContainText("• Send the notes");
  await tabs.getByRole("tab", { name: /Spell the names/ }).click();
  await expect(page.getByRole("tabpanel")).toContainText("Kubernetes");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("tabpanel")).toBeFocused();
});

test("v2 fits narrow phones through large desktops and keeps the design column", async ({
  page,
}) => {
  await page.goto("./");
  for (const width of [320, 360, 390, 700, 820, 1050, 1440, 1920]) {
    await page.setViewportSize({ width, height: 900 });
    await page.evaluate(async () => {
      await document.fonts.ready;
      await new Promise(requestAnimationFrame);
    });
    await expect
      .poll(
        () =>
          page.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth,
          ),
        { message: `width ${width}` },
      )
      .toBe(true);
  }
  await page.setViewportSize({ width: 1440, height: 900 });
  const column = await page.locator(".hero").boundingBox();
  expect(column?.x).toBe(160);
  expect(column?.width).toBe(1120);
});
