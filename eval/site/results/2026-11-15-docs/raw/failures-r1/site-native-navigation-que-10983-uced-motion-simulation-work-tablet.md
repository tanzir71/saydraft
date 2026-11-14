# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: site.spec.ts >> native navigation, questions, and reduced-motion simulation work
- Location: tests\site.spec.ts:51:1

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByText('Saydraft is in development.')
Expected: visible
Error: strict mode violation: getByText('Saydraft is in development.') resolved to 2 elements:
    1) <p class="notice">Saydraft is in development. A signed installer an…</p> aka getByText('Saydraft is in development. A')
    2) <p>Saydraft is in development. Use the current sourc…</p> aka getByText('Saydraft is in development. Use the current source instructions and check')

Call log:
  - Expect "toBeVisible" getByText('Saydraft is in development.') with timeout 5000ms
  - waiting for getByText('Saydraft is in development.')

```

# Page snapshot

```yaml
- generic [active] [ref=f1e1]:
  - link "Skip to content" [ref=f1e2] [cursor=pointer]:
    - /url: "#main"
  - banner [ref=f1e3]:
    - navigation "Main navigation" [ref=f1e4]:
      - link "Saydraft home" [ref=f1e5] [cursor=pointer]:
        - /url: /saydraft/
        - text: Saydraft
        - generic [aria-hidden] [ref=f1e6]: ✳
      - link "Get Saydraft" [ref=f1e7] [cursor=pointer]:
        - /url: /saydraft/download/
        - text: Get Saydraft
        - generic [aria-hidden] [ref=f1e8]: ↗
      - group [ref=f1e9]:
        - generic "Navigation menu" [ref=f1e10] [cursor=pointer]:
          - generic [aria-hidden] [ref=f1e11]: ☰
  - main [ref=f1e12]:
    - navigation "Breadcrumb" [ref=f1e13]:
      - link "Saydraft" [ref=f1e14] [cursor=pointer]:
        - /url: /saydraft/
      - generic [aria-hidden] [ref=f1e15]: /
      - generic [ref=f1e16]: Make it your own.
    - paragraph [ref=f1e17]: A home for your next thought
    - heading [level=1] [ref=f1e18]:
      - text: Make it
      - emphasis [ref=f1e19]: your own.
    - paragraph [ref=f1e20]:
      - text: Facts checked
      - time [ref=f1e21]: 2026-11-14
      - text: . Product plans and features can change.
    - navigation "On this page" [ref=f1e22]:
      - paragraph [ref=f1e23]: On this page
      - list [ref=f1e24]:
        - listitem [ref=f1e25]:
          - link "Run from source" [ref=f1e26] [cursor=pointer]:
            - /url: "#run-from-source"
        - listitem [ref=f1e27]:
          - link "Set up once. Then go offline." [ref=f1e28] [cursor=pointer]:
            - /url: "#set-up-once-then-go-offline"
        - listitem [ref=f1e29]:
          - link "Speech model downloads" [ref=f1e30] [cursor=pointer]:
            - /url: "#speech-model-downloads"
        - listitem [ref=f1e31]:
          - link "Looking for a packaged build?" [ref=f1e32] [cursor=pointer]:
            - /url: "#looking-for-a-packaged-build"
    - article [ref=f1e33]:
      - paragraph [ref=f1e34]: Saydraft is in development. A signed installer and package-manager releases are being prepared. You can run the current code from source today.
      - heading "Run from source" [level=2] [ref=f1e35]
      - paragraph [ref=f1e36]: "You’ll need Windows 10 or 11, 64-bit Python 3.13, Git, a microphone and disk space for your selected models. In PowerShell:"
      - figure "PowerShell Copy command" [ref=f1e37]:
        - generic [ref=f1e38]:
          - generic [ref=f1e39]: PowerShell
          - button "Copy command" [ref=f1e40] [cursor=pointer]
        - code [ref=f1e42]: git clone https://github.com/tanzir71/saydraft.git cd saydraft py -3.13 -m venv .venv .venv\Scripts\python -m pip install -r requirements.txt .venv\Scripts\python -m saydraft
        - status
      - heading "Set up once. Then go offline." [level=2] [ref=f1e43]
      - paragraph [ref=f1e44]:
        - text: Review the recommended model, size and license, then start its download in setup. Progress and pause/resume are available. Later launches reuse your installed files. The
        - link "setup walkthrough" [ref=f1e45] [cursor=pointer]:
          - /url: /saydraft/docs/getting-started/
        - text: covers microphone selection, models, shortcuts and a first practice draft.
      - paragraph [ref=f1e46]:
        - text: Thai, Chinese, Korean, Japanese, Hindi, Urdu, Indonesian, Malay, Bengali and Arabic use the optional shared All languages model. Download it once; there are no separate language packs. Portuguese, including Brazilian Portuguese, is also covered by the default model. Review
        - link "language and model choices" [ref=f1e47] [cursor=pointer]:
          - /url: /saydraft/docs/languages/
        - text: before choosing a package.
      - heading "Speech model downloads" [level=2] [ref=f1e48]
      - paragraph [ref=f1e49]: These transfer sizes come from the pinned app catalog at build time. MB means 1,000,000 bytes. Verified cache entries can reduce what you download; disk use also includes installed files, temporary transfers and optional retained audio.
      - table [ref=f1e50]:
        - rowgroup [ref=f1e51]:
          - row [ref=f1e52]:
            - columnheader "Model or package" [ref=f1e53]
            - columnheader "Transfer" [ref=f1e54]
            - columnheader "License" [ref=f1e55]
        - rowgroup [ref=f1e56]:
          - row [ref=f1e57]:
            - 'rowheader "Default: Parakeet v3 + language detector" [ref=f1e58]':
              - 'link "Default: Parakeet v3 + language detector" [ref=f1e59] [cursor=pointer]':
                - /url: https://huggingface.co/csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8
            - cell "773.4 MB" [ref=f1e60]
            - cell "CC-BY-4.0 + MIT" [ref=f1e61]
          - row [ref=f1e62]:
            - 'rowheader "English max: Parakeet v2" [ref=f1e63]':
              - 'link "English max: Parakeet v2" [ref=f1e64] [cursor=pointer]':
                - /url: https://huggingface.co/csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8
            - cell "661.3 MB" [ref=f1e65]
            - cell "CC-BY-4.0" [ref=f1e66]
          - row [ref=f1e67]:
            - rowheader "Whisper base" [ref=f1e68]:
              - link "Whisper base" [ref=f1e69] [cursor=pointer]:
                - /url: https://huggingface.co/Systran/faster-whisper-base
            - cell "147.9 MB" [ref=f1e70]
            - cell "MIT" [ref=f1e71]
          - row [ref=f1e72]:
            - rowheader "Whisper small" [ref=f1e73]:
              - link "Whisper small" [ref=f1e74] [cursor=pointer]:
                - /url: https://huggingface.co/Systran/faster-whisper-small
            - cell "486.2 MB" [ref=f1e75]
            - cell "MIT" [ref=f1e76]
          - row [ref=f1e77]:
            - rowheader "Whisper medium" [ref=f1e78]:
              - link "Whisper medium" [ref=f1e79] [cursor=pointer]:
                - /url: https://huggingface.co/Systran/faster-whisper-medium
            - cell "1530.6 MB" [ref=f1e80]
            - cell "MIT" [ref=f1e81]
          - row [ref=f1e82]:
            - 'rowheader "All languages: Whisper turbo" [ref=f1e83]':
              - 'link "All languages: Whisper turbo" [ref=f1e84] [cursor=pointer]':
                - /url: https://huggingface.co/dropbox-dash/faster-whisper-large-v3-turbo
            - cell "1621.7 MB" [ref=f1e85]
            - cell "MIT" [ref=f1e86]
          - row [ref=f1e87]:
            - rowheader "Optional Silero speech detection" [ref=f1e88]:
              - link "Optional Silero speech detection" [ref=f1e89] [cursor=pointer]:
                - /url: https://github.com/snakers4/silero-vad/tree/v5.0
            - cell "2.3 MB" [ref=f1e90]
            - cell "MIT" [ref=f1e91]
          - row [ref=f1e92]:
            - rowheader "Optional GTCRN quiet-speech enhancement" [ref=f1e93]:
              - link "Optional GTCRN quiet-speech enhancement" [ref=f1e94] [cursor=pointer]:
                - /url: https://github.com/Xiaobin-Rong/gtcrn
            - cell "0.54 MB" [ref=f1e95]
            - cell "MIT" [ref=f1e96]
      - paragraph [ref=f1e97]:
        - text: The default package includes its language detector. Optional AI cleanup, live preview and editing features have separate model/runtime requirements. See
        - link "local models" [ref=f1e98] [cursor=pointer]:
          - /url: /saydraft/docs/models/
        - text: for those choices and their limits. Selecting a language never starts a transfer.
      - heading "Looking for a packaged build?" [level=2] [ref=f1e99]
      - article [ref=f1e100]:
        - heading "Saydraft for Windows" [level=2] [ref=f1e101]
        - paragraph [ref=f1e102]: A packaged release is being prepared. Run the current code from source and review setup first.
        - link "View the source" [ref=f1e103] [cursor=pointer]:
          - /url: https://github.com/tanzir71/saydraft
          - text: View the source
          - generic [aria-hidden] [ref=f1e104]: ↗
      - paragraph [ref=f1e105]:
        - text: Check
        - link "GitHub Releases" [ref=f1e106] [cursor=pointer]:
          - /url: https://github.com/tanzir71/saydraft/releases
        - text: for published artifacts. Installer checksums, signing details and winget/Scoop commands will appear here when those releases are available.
    - region "A few useful answers." [ref=f1e107]:
      - heading "A few useful answers." [level=2] [ref=f1e108]
      - generic [ref=f1e109]:
        - group [ref=f1e110]:
          - generic "Is a signed Windows installer available here?" [ref=f1e111] [cursor=pointer]:
            - text: Is a signed Windows installer available here?
            - generic [aria-hidden] [ref=f1e112]: +
        - group [ref=f1e113]:
          - generic "Will models download automatically?" [ref=f1e114] [cursor=pointer]:
            - text: Will models download automatically?
            - generic [aria-hidden] [ref=f1e115]: +
    - region "Sources and further reading" [ref=f1e116]:
      - heading "Sources and further reading" [level=2] [ref=f1e117]
      - list [ref=f1e118]:
        - listitem [ref=f1e119]:
          - link "Current setup and release status ↗" [ref=f1e120] [cursor=pointer]:
            - /url: https://github.com/tanzir71/saydraft/blob/main/readme.md
        - listitem [ref=f1e121]:
          - link "Pinned model files, sizes and licenses ↗" [ref=f1e122] [cursor=pointer]:
            - /url: https://github.com/tanzir71/saydraft/blob/main/saydraft/models/manifest.json
    - complementary [ref=f1e123]:
      - heading "Ready for your first few words?" [level=2] [ref=f1e124]
      - paragraph [ref=f1e125]: Choose a compatible model, review its size and license, then try a short draft.
      - link "Read the setup guide" [ref=f1e126] [cursor=pointer]:
        - /url: /saydraft/docs/getting-started/
        - text: Read the setup guide
        - generic [aria-hidden] [ref=f1e127]: ↗
    - navigation "More guides" [ref=f1e128]:
      - heading "Keep reading." [level=2] [ref=f1e129]
      - list [ref=f1e130]:
        - listitem [ref=f1e131]:
          - link "Offline dictation guide" [ref=f1e132] [cursor=pointer]:
            - /url: /saydraft/offline-dictation-windows/
        - listitem [ref=f1e133]:
          - link "Dictation for developers" [ref=f1e134] [cursor=pointer]:
            - /url: /saydraft/dictation-for-developers/
        - listitem [ref=f1e135]:
          - link "Wispr Flow alternative" [ref=f1e136] [cursor=pointer]:
            - /url: /saydraft/wispr-flow-alternative/
        - listitem [ref=f1e137]:
          - link "Typeless alternative" [ref=f1e138] [cursor=pointer]:
            - /url: /saydraft/typeless-alternative/
        - listitem [ref=f1e139]:
          - link "Superwhisper alternative" [ref=f1e140] [cursor=pointer]:
            - /url: /saydraft/superwhisper-alternative-windows/
        - listitem [ref=f1e141]:
          - link "Windows voice typing alternative" [ref=f1e142] [cursor=pointer]:
            - /url: /saydraft/windows-voice-typing-alternative/
        - listitem [ref=f1e143]:
          - link "Dragon alternative" [ref=f1e144] [cursor=pointer]:
            - /url: /saydraft/dragon-alternative/
        - listitem [ref=f1e145]:
          - link "Changelog" [ref=f1e146] [cursor=pointer]:
            - /url: /saydraft/changelog/
  - contentinfo [ref=f1e147]:
    - link "Saydraft" [ref=f1e148] [cursor=pointer]:
      - /url: /saydraft/
      - text: Saydraft✳
    - paragraph [ref=f1e149]: Your words. Your machine.
    - generic [ref=f1e150]:
      - link "Getting started" [ref=f1e151] [cursor=pointer]:
        - /url: /saydraft/docs/getting-started/
      - link "Languages" [ref=f1e152] [cursor=pointer]:
        - /url: /saydraft/languages/
      - link "Offline dictation guide" [ref=f1e153] [cursor=pointer]:
        - /url: /saydraft/offline-dictation-windows/
      - link "For developers" [ref=f1e154] [cursor=pointer]:
        - /url: /saydraft/dictation-for-developers/
      - link "Privacy" [ref=f1e155] [cursor=pointer]:
        - /url: /saydraft/privacy/
      - link "Credits" [ref=f1e156] [cursor=pointer]:
        - /url: /saydraft/credits/
      - link "Changelog" [ref=f1e157] [cursor=pointer]:
        - /url: /saydraft/changelog/
      - link "MIT license ↗" [ref=f1e158] [cursor=pointer]:
        - /url: https://github.com/tanzir71/saydraft/blob/main/LICENSE
    - navigation "Compare dictation tools" [ref=f1e159]:
      - generic [ref=f1e160]: Compare
      - link "Wispr Flow" [ref=f1e161] [cursor=pointer]:
        - /url: /saydraft/wispr-flow-alternative/
      - link "Typeless" [ref=f1e162] [cursor=pointer]:
        - /url: /saydraft/typeless-alternative/
      - link "Superwhisper" [ref=f1e163] [cursor=pointer]:
        - /url: /saydraft/superwhisper-alternative-windows/
      - link "Windows voice typing" [ref=f1e164] [cursor=pointer]:
        - /url: /saydraft/windows-voice-typing-alternative/
      - link "Dragon" [ref=f1e165] [cursor=pointer]:
        - /url: /saydraft/dragon-alternative/
    - generic [ref=f1e166]:
      - generic [ref=f1e167]: Free, open-source dictation for Windows.
      - navigation "Creator links" [ref=f1e168]:
        - link "Built by tanziro.com" [ref=f1e169] [cursor=pointer]:
          - /url: https://tanziro.com
        - link "Support Saydraft ↗" [ref=f1e170] [cursor=pointer]:
          - /url: https://buymeacoffee.com/tanzir
```

# Test source

```ts
  1   | import { test, expect } from '@playwright/test';
  2   | import { gzipSync } from 'node:zlib';
  3   | import { readFileSync, readdirSync } from 'node:fs';
  4   | import { join } from 'node:path';
  5   | import { HtmlValidate } from 'html-validate';
  6   | import { publicPages } from '../src/data/languages';
  7   | import { guideRoutes } from '../src/data/guides';
  8   | import { siteOrigin } from '../test-ports';
  9   | 
  10  | test('home is local, responsive, and light on JavaScript', async ({ page, request }, testInfo) => {
  11  |   const external: string[] = [];
  12  |   const errors: string[] = [];
  13  |   page.on('pageerror', (error) => errors.push(error.message));
  14  |   await page.route('**/*', (route) => {
  15  |     if (new URL(route.request().url()).origin !== siteOrigin) { external.push(route.request().url()); return route.abort(); }
  16  |     return route.continue();
  17  |   });
  18  |   await page.goto('./');
  19  |   await page.evaluate(() => document.fonts.ready);
  20  |   await expect(page.getByRole('heading', { level: 1 })).toHaveText('Speak messy.Paste polished.');
  21  |   expect(await page.getByRole('heading', { level: 1 }).evaluate((heading) => parseFloat(getComputedStyle(heading).fontSize))).toBeGreaterThanOrEqual(56);
  22  |   expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  23  |   for (const selector of ['.credits-sheet', '.thought-sheet', '.final-sheet']) {
  24  |     const panel = await page.locator(selector).boundingBox();
  25  |     const content = await page.locator(`${selector} > .container`).boundingBox();
  26  |     expect(panel && content).toBeTruthy();
  27  |     expect(panel!.x).toBeGreaterThanOrEqual(16);
  28  |     expect(panel!.x + panel!.width).toBeLessThanOrEqual(page.viewportSize()!.width - 16);
  29  |     expect(content!.x).toBeGreaterThan(panel!.x);
  30  |   }
  31  |   await expect(page.getByRole('contentinfo').getByRole('link', { name: 'Built by tanziro.com' })).toHaveAttribute('href', 'https://tanziro.com');
  32  |   await expect(page.getByRole('contentinfo').getByRole('link', { name: 'Support Saydraft' })).toHaveAttribute('href', 'https://buymeacoffee.com/tanzir');
  33  |   const scripts = await page.locator('script[src]').evaluateAll((nodes) => nodes.map((node) => (node as HTMLScriptElement).src));
  34  |   const inline = await page.locator('script:not([src]):not([type="application/ld+json"])').allTextContents();
  35  |   let bytes = gzipSync(inline.join('\n')).length;
  36  |   for (const src of scripts) { const response = await request.get(src); expect(response.ok()).toBe(true); bytes += gzipSync(await response.body()).length; }
  37  |   expect(bytes).toBeLessThan(60 * 1024);
  38  |   expect(external).toEqual([]);
  39  |   expect(errors).toEqual([]);
  40  |   await expect(page).toHaveScreenshot('home.png', { fullPage: true, animations: 'disabled' });
  41  |   const viewport = testInfo.outputPath('viewport.png');
  42  |   await page.screenshot({ path: viewport, animations: 'disabled' });
  43  |   await testInfo.attach('Viewport', { path: viewport, contentType: 'image/png' });
  44  |   for (const [name, selector] of [['sheet', '.credits-sheet'], ['footer', '.site-footer']]) {
  45  |     const path = testInfo.outputPath(`${name}.png`);
  46  |     await page.locator(selector).screenshot({ path, animations: 'disabled' });
  47  |     await testInfo.attach(name, { path, contentType: 'image/png' });
  48  |   }
  49  | });
  50  | 
  51  | test('native navigation, questions, and reduced-motion simulation work', async ({ page }) => {
  52  |   await page.goto('./');
  53  |   await page.getByRole('button', { name: 'Play the example' }).click();
  54  |   await expect(page.getByRole('status')).toContainText('Example finished');
  55  |   await expect(page.locator('[data-bar-demo]')).toHaveAttribute('data-state', 'inserted');
  56  |   const question = page.locator('summary').filter({ hasText: 'Does my voice leave my PC?' });
  57  |   await question.click();
  58  |   await expect(page.getByText('Speech recognition and text cleanup run locally.', { exact: false })).toBeVisible();
  59  |   const menu = page.getByLabel('Navigation menu');
  60  |   if (await menu.isVisible()) { await menu.click(); await expect(page.getByRole('link', { name: 'Features', exact: true })).toBeVisible(); }
  61  |   await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'Get Saydraft' }).click();
  62  |   await expect(page).toHaveURL(/\/saydraft\/download\/$/);
> 63  |   await expect(page.getByText('Saydraft is in development.', { exact: false })).toBeVisible();
      |                                                                                 ^ Error: expect(locator).toBeVisible() failed
  64  | });
  65  | 
  66  | test('all public pages have working local links and unique metadata', async ({ page, request }) => {
  67  |   const pages = publicPages;
  68  |   const titles = new Set<string>();
  69  |   const descriptions = new Set<string>();
  70  |   const headings = new Set<string>();
  71  |   for (const path of pages) {
  72  |     await page.goto(`./${path}`);
  73  |     await expect(page.getByRole('heading', { level: 1 })).toHaveCount(1);
  74  |     const heading = (await page.getByRole('heading', { level: 1 }).innerText()).trim();
  75  |     expect(heading.length).toBeGreaterThan(0);
  76  |     headings.add(heading);
  77  |     titles.add(await page.title());
  78  |     descriptions.add(await page.locator('meta[name="description"]').getAttribute('content') ?? '');
  79  |     expect(await page.locator('link[rel="canonical"]').getAttribute('href')).toBe(`https://tanzir71.github.io/saydraft/${path}`);
  80  |     const links = await page.locator('a[href]').evaluateAll((nodes) => [...new Set(nodes.map((node) => (node as HTMLAnchorElement).href))]);
  81  |     for (const href of links.filter((link) => new URL(link).origin === siteOrigin)) {
  82  |       expect((await request.get(href)).ok(), href).toBe(true);
  83  |     }
  84  |   }
  85  |   expect(titles.size).toBe(pages.length);
  86  |   expect(descriptions.size).toBe(pages.length);
  87  |   expect(headings.size).toBe(pages.length);
  88  | });
  89  | 
  90  | test('guide keyboard navigation exposes the skip link and reaches main content', async ({ page }) => {
  91  |   await page.goto('./wispr-flow-alternative/');
  92  |   await page.keyboard.press('Tab');
  93  |   await expect(page.getByRole('link', { name: 'Skip to content' })).toBeFocused();
  94  |   await expect(page.getByRole('link', { name: 'Skip to content' })).toBeInViewport();
  95  |   await page.keyboard.press('Enter');
  96  |   await expect(page).toHaveURL(/#main$/);
  97  | });
  98  | 
  99  | test('dated guides have visible sources, linked schemas and local-only page loads', async ({ page, request }) => {
  100 |   const external: string[] = [];
  101 |   await page.route('**/*', (route) => {
  102 |     if (new URL(route.request().url()).origin !== siteOrigin) {
  103 |       external.push(route.request().url());
  104 |       return route.abort();
  105 |     }
  106 |     return route.continue();
  107 |   });
  108 |   for (const { slug } of guideRoutes) {
  109 |     await page.goto(`./${slug}/`);
  110 |     await expect(page.locator('.guide-verified time')).toHaveAttribute('datetime', /^\d{4}-\d{2}-\d{2}$/);
  111 |     await expect(page.locator('.guide-sources a').first()).toBeVisible();
  112 |     await expect(page.locator('.guide-next a')).toHaveAttribute('href', '/saydraft/download/');
  113 |     const contrast = await page.locator('.guide-next a').evaluate((button) => {
  114 |       const style = getComputedStyle(button);
  115 |       function luminance(value: string) {
  116 |         const channels = value.match(/\d+(?:\.\d+)?/g)!.slice(0, 3).map(Number).map((n) => n / 255);
  117 |         const values = channels.map((n) => n <= .04045 ? n / 12.92 : ((n + .055) / 1.055) ** 2.4);
  118 |         return values[0] * .2126 + values[1] * .7152 + values[2] * .0722;
  119 |       }
  120 |       const foreground = luminance(style.color), background = luminance(style.backgroundColor);
  121 |       return (Math.max(foreground, background) + .05) / (Math.min(foreground, background) + .05);
  122 |     });
  123 |     expect(contrast).toBeGreaterThanOrEqual(4.5);
  124 |     expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  125 |     const schemas = (await page.locator('script[type="application/ld+json"]').allTextContents()).map((text) => JSON.parse(text));
  126 |     expect(schemas.some((schema) => schema['@type'] === 'BreadcrumbList')).toBe(true);
  127 |     if (slug !== 'changelog') {
  128 |       expect(schemas.find((schema) => schema['@type'] === 'FAQPage').mainEntity.length).toBeGreaterThan(0);
  129 |       const answer = page.locator('.guide-faq summary').first();
  130 |       await answer.click();
  131 |       await expect(page.locator('.guide-faq details').first()).toHaveAttribute('open', '');
  132 |       await answer.click();
  133 |     }
  134 |     await expect(page.locator('.skip-link')).not.toBeInViewport();
  135 |     await page.evaluate(async () => { await document.fonts.ready; window.scrollTo(0, 0); });
  136 |     await page.screenshot({ path: test.info().outputPath(`${slug}-viewport.png`), animations: 'disabled' });
  137 |     await page.screenshot({ path: test.info().outputPath(`${slug}.png`), fullPage: true, animations: 'disabled' });
  138 |   }
  139 |   expect(external).toEqual([]);
  140 |   const sitemap = await (await request.get('/saydraft/sitemap.xml')).text();
  141 |   for (const { slug } of guideRoutes) expect(sitemap).toContain(`https://tanzir71.github.io/saydraft/${slug}/`);
  142 | });
  143 | 
  144 | test('language guides are linked, indexable and accurately describe shared models', async ({ page, request }) => {
  145 |   const guides = [
  146 |     ['arabic', 'Arabic', 'ar'], ['bengali', 'Bengali', 'bn'],
  147 |     ['brazilian-portuguese', 'Brazilian Portuguese', 'pt'], ['chinese', 'Chinese (Mandarin)', 'zh'],
  148 |     ['filipino-tagalog', 'Filipino / Tagalog', 'tl'], ['french', 'French', 'fr'],
  149 |     ['german', 'German', 'de'], ['hindi', 'Hindi', 'hi'], ['indonesian', 'Indonesian', 'id'],
  150 |     ['japanese', 'Japanese', 'ja'], ['korean', 'Korean', 'ko'], ['malay', 'Malay', 'ms'],
  151 |     ['persian', 'Persian (Farsi)', 'fa'], ['spanish', 'Spanish', 'es'], ['tamil', 'Tamil', 'ta'],
  152 |     ['telugu', 'Telugu', 'te'], ['thai', 'Thai', 'th'], ['urdu', 'Urdu', 'ur'],
  153 |     ['vietnamese', 'Vietnamese', 'vi'],
  154 |   ];
  155 |   await page.goto('./');
  156 |   const orderedLabels = guides.map(([, name]) => `${name} voice typing ↗`);
  157 |   await expect(page.locator('.language-links a')).toHaveText(orderedLabels);
  158 |   for (const [slug, name] of guides) {
  159 |     await expect(page.locator('.language-section').getByRole('link', { name: `${name} voice typing` })).toHaveAttribute('href', `/saydraft/languages/${slug}/`);
  160 |   }
  161 |   await page.locator('.language-section').getByRole('link', { name: 'Korean voice typing' }).click();
  162 |   await expect(page).toHaveURL(/\/languages\/korean\/$/);
  163 |   await page.goto('./languages/');
```