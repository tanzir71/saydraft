import type { Page } from '@playwright/test';

/** Flat token surfaces let the rendered foreground/background be checked directly. */
export async function contrastFailures(page: Page) {
  return page.locator('#storybook-root').evaluate((root) => {
    type Color = [number, number, number, number];
    const color = (value: string): Color => {
      const parts = value.match(/[\d.]+/g)?.map(Number) ?? [0, 0, 0, 0];
      return [parts[0], parts[1], parts[2], parts[3] ?? 1];
    };
    const blend = (front: Color, back: Color): Color => [
      front[0] * front[3] + back[0] * (1 - front[3]), front[1] * front[3] + back[1] * (1 - front[3]),
      front[2] * front[3] + back[2] * (1 - front[3]), 1,
    ];
    const luminance = (rgb: Color) => rgb.slice(0, 3).reduce((sum, value, index) => {
      const channel = value / 255;
      return sum + (channel <= .04045 ? channel / 12.92 : ((channel + .055) / 1.055) ** 2.4) * [.2126, .7152, .0722][index];
    }, 0);
    const failures: { text: string; ratio: number; required: number }[] = [];
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const element = node.parentElement;
      const text = node.textContent?.trim();
      if (!element || !text || element.closest('[aria-hidden="true"],svg,script,style')) continue;
      const range = document.createRange(); range.selectNodeContents(node);
      if (!range.getClientRects().length) continue;
      const css = getComputedStyle(element);
      if (css.visibility !== 'visible') continue;
      const ancestors: Element[] = [];
      for (let parent: Element | null = element; parent; parent = parent.parentElement) ancestors.push(parent);
      let background: Color = [255, 255, 255, 1];
      for (const ancestor of ancestors.reverse()) background = blend(color(getComputedStyle(ancestor).backgroundColor), background);
      const foreground = blend(color(css.color), background);
      const values = [luminance(foreground), luminance(background)].sort((a, b) => b - a);
      const ratio = (values[0] + .05) / (values[1] + .05);
      const large = parseFloat(css.fontSize) >= 24 || parseFloat(css.fontSize) >= 18.66 && Number(css.fontWeight) >= 700;
      const required = large ? 3 : 4.5;
      if (ratio + .01 < required) failures.push({ text: text.slice(0, 100), ratio, required });
    }
    return failures;
  });
}
