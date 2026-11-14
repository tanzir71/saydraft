# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: docs.spec.ts >> all documentation and resources are readable, dated and navigable
- Location: tests\docs.spec.ts:6:1

# Error details

```
Error: expect(received).toBeGreaterThan(expected)

Expected: > 500
Received:   461
```

# Page snapshot

```yaml
- generic [active] [ref=f10e1]:
  - link "Skip to content" [ref=f10e2] [cursor=pointer]:
    - /url: "#main"
  - banner [ref=f10e3]:
    - navigation "Main navigation" [ref=f10e4]:
      - link "Saydraft home" [ref=f10e5] [cursor=pointer]:
        - /url: /saydraft/
        - text: Saydraft
        - generic [aria-hidden] [ref=f10e6]: ✳
      - link "Get Saydraft" [ref=f10e7] [cursor=pointer]:
        - /url: /saydraft/download/
        - text: Get Saydraft
        - generic [aria-hidden] [ref=f10e8]: ↗
      - group [ref=f10e9]:
        - generic "Navigation menu" [ref=f10e10] [cursor=pointer]:
          - generic [aria-hidden] [ref=f10e11]: ☰
  - main [ref=f10e12]:
    - navigation "Breadcrumb" [ref=f10e13]:
      - link "Saydraft" [ref=f10e14] [cursor=pointer]:
        - /url: /saydraft/
      - generic [aria-hidden] [ref=f10e15]: /
      - link "Docs" [ref=f10e16] [cursor=pointer]:
        - /url: /saydraft/docs/
      - generic [aria-hidden] [ref=f10e17]: /
      - generic [ref=f10e18]: Saydraft questions, answered.
    - paragraph [ref=f10e19]: A few useful answers
    - heading [level=1] [ref=f10e20]:
      - text: Saydraft questions,
      - emphasis [ref=f10e21]: answered.
    - paragraph [ref=f10e22]:
      - text: Facts checked
      - time [ref=f10e23]: 2026-11-14
      - text: . Product plans and features can change.
    - navigation "Documentation" [ref=f10e24]:
      - list [ref=f10e25]:
        - listitem [ref=f10e26]:
          - link "Documentation" [ref=f10e27] [cursor=pointer]:
            - /url: /saydraft/docs/
        - listitem [ref=f10e28]:
          - link "Getting started" [ref=f10e29] [cursor=pointer]:
            - /url: /saydraft/docs/getting-started/
        - listitem [ref=f10e30]:
          - link "Shortcuts" [ref=f10e31] [cursor=pointer]:
            - /url: /saydraft/docs/shortcuts/
        - listitem [ref=f10e32]:
          - link "Styles and cleanup" [ref=f10e33] [cursor=pointer]:
            - /url: /saydraft/docs/styles/
        - listitem [ref=f10e34]:
          - link "Dictionary" [ref=f10e35] [cursor=pointer]:
            - /url: /saydraft/docs/dictionary/
        - listitem [ref=f10e36]:
          - link "Local models" [ref=f10e37] [cursor=pointer]:
            - /url: /saydraft/docs/models/
        - listitem [ref=f10e38]:
          - link "Languages" [ref=f10e39] [cursor=pointer]:
            - /url: /saydraft/docs/languages/
        - listitem [ref=f10e40]:
          - link "Command Mode" [ref=f10e41] [cursor=pointer]:
            - /url: /saydraft/docs/command-mode/
        - listitem [ref=f10e42]:
          - link "Verify offline" [ref=f10e43] [cursor=pointer]:
            - /url: /saydraft/docs/privacy/verify-offline/
        - listitem [ref=f10e44]:
          - link "Troubleshooting" [ref=f10e45] [cursor=pointer]:
            - /url: /saydraft/docs/troubleshooting/
        - listitem [ref=f10e46]:
          - link "FAQ" [ref=f10e47] [cursor=pointer]:
            - /url: /saydraft/docs/faq/
    - navigation "On this page" [ref=f10e48]:
      - paragraph [ref=f10e49]: On this page
      - list [ref=f10e50]:
        - listitem [ref=f10e51]:
          - link "Start with a setup that fits" [ref=f10e52] [cursor=pointer]:
            - /url: "#start-with-a-setup-that-fits"
        - listitem [ref=f10e53]:
          - link "Find more detail" [ref=f10e54] [cursor=pointer]:
            - /url: "#find-more-detail"
    - article [ref=f10e55]:
      - heading "Start with a setup that fits" [level=2] [ref=f10e56]
      - paragraph [ref=f10e57]:
        - text: Use
        - link "Getting started" [ref=f10e58] [cursor=pointer]:
          - /url: /saydraft/docs/getting-started/
        - text: for the first run, then review
        - link "models" [ref=f10e59] [cursor=pointer]:
          - /url: /saydraft/docs/models/
        - text: and
        - link "language compatibility" [ref=f10e60] [cursor=pointer]:
          - /url: /saydraft/docs/languages/
        - text: . Saydraft’s current app target is Windows 10 and 11, and it remains in development.
      - heading "Find more detail" [level=2] [ref=f10e61]
      - paragraph [ref=f10e62]:
        - text: For saved data, network exceptions and clipboard boundaries, read
        - link "Privacy" [ref=f10e63] [cursor=pointer]:
          - /url: /saydraft/privacy/
        - text: . For input or delivery issues, use
        - link "Troubleshooting" [ref=f10e64] [cursor=pointer]:
          - /url: /saydraft/docs/troubleshooting/
        - text: . The questions below summarize those guides; the linked source records contain the implementation and measured limits.
    - region "A few useful answers." [ref=f10e65]:
      - heading "A few useful answers." [level=2] [ref=f10e66]
      - generic [ref=f10e67]:
        - group [ref=f10e68]:
          - generic "Is Saydraft free?" [ref=f10e69] [cursor=pointer]:
            - text: Is Saydraft free?
            - generic [aria-hidden] [ref=f10e70]: +
        - group [ref=f10e71]:
          - generic "Do I need an account or subscription?" [ref=f10e72] [cursor=pointer]:
            - text: Do I need an account or subscription?
            - generic [aria-hidden] [ref=f10e73]: +
        - group [ref=f10e74]:
          - generic "Can I dictate without internet?" [ref=f10e75] [cursor=pointer]:
            - text: Can I dictate without internet?
            - generic [aria-hidden] [ref=f10e76]: +
        - group [ref=f10e77]:
          - generic "Are Spanish and Brazilian Portuguese included?" [ref=f10e78] [cursor=pointer]:
            - text: Are Spanish and Brazilian Portuguese included?
            - generic [aria-hidden] [ref=f10e79]: +
        - group [ref=f10e80]:
          - generic "What about Arabic, Bengali, Chinese, Japanese, Korean and Thai?" [ref=f10e81] [cursor=pointer]:
            - text: What about Arabic, Bengali, Chinese, Japanese, Korean and Thai?
            - generic [aria-hidden] [ref=f10e82]: +
        - group [ref=f10e83]:
          - generic "Will it get every word right?" [ref=f10e84] [cursor=pointer]:
            - text: Will it get every word right?
            - generic [aria-hidden] [ref=f10e85]: +
        - group [ref=f10e86]:
          - generic "Do I need an AI cleanup model?" [ref=f10e87] [cursor=pointer]:
            - text: Do I need an AI cleanup model?
            - generic [aria-hidden] [ref=f10e88]: +
        - group [ref=f10e89]:
          - generic "Is Whisper mode a different speech model?" [ref=f10e90] [cursor=pointer]:
            - text: Is Whisper mode a different speech model?
            - generic [aria-hidden] [ref=f10e91]: +
        - group [ref=f10e92]:
          - generic "Are recordings kept?" [ref=f10e93] [cursor=pointer]:
            - text: Are recordings kept?
            - generic [aria-hidden] [ref=f10e94]: +
        - group [ref=f10e95]:
          - generic "Does the website listen to me?" [ref=f10e96] [cursor=pointer]:
            - text: Does the website listen to me?
            - generic [aria-hidden] [ref=f10e97]: +
    - region "Sources and further reading" [ref=f10e98]:
      - heading "Sources and further reading" [level=2] [ref=f10e99]
      - list [ref=f10e100]:
        - listitem [ref=f10e101]:
          - link "Current feature and release status ↗" [ref=f10e102] [cursor=pointer]:
            - /url: https://github.com/tanzir71/saydraft/blob/main/readme.md
        - listitem [ref=f10e103]:
          - link "Speech language coverage and accuracy limits ↗" [ref=f10e104] [cursor=pointer]:
            - /url: https://github.com/tanzir71/saydraft/blob/main/docs/LANGUAGES.md
        - listitem [ref=f10e105]:
          - link "Privacy and explicit network actions ↗" [ref=f10e106] [cursor=pointer]:
            - /url: https://github.com/tanzir71/saydraft/blob/main/docs/PRIVACY.md
    - complementary [ref=f10e107]:
      - heading "Try it with your own words." [level=2] [ref=f10e108]
      - paragraph [ref=f10e109]: Saydraft is in development and available from source. Review the setup status, model sizes and measured limits before choosing it for your workflow.
      - link "Get Saydraft" [ref=f10e110] [cursor=pointer]:
        - /url: /saydraft/download/
        - text: Get Saydraft
        - generic [aria-hidden] [ref=f10e111]: ↗
    - navigation "More guides" [ref=f10e112]:
      - heading "Keep reading." [level=2] [ref=f10e113]
      - list [ref=f10e114]:
        - listitem [ref=f10e115]:
          - link "Documentation" [ref=f10e116] [cursor=pointer]:
            - /url: /saydraft/docs/
        - listitem [ref=f10e117]:
          - link "Getting started" [ref=f10e118] [cursor=pointer]:
            - /url: /saydraft/docs/getting-started/
        - listitem [ref=f10e119]:
          - link "Shortcuts" [ref=f10e120] [cursor=pointer]:
            - /url: /saydraft/docs/shortcuts/
        - listitem [ref=f10e121]:
          - link "Styles and cleanup" [ref=f10e122] [cursor=pointer]:
            - /url: /saydraft/docs/styles/
        - listitem [ref=f10e123]:
          - link "Dictionary" [ref=f10e124] [cursor=pointer]:
            - /url: /saydraft/docs/dictionary/
        - listitem [ref=f10e125]:
          - link "Local models" [ref=f10e126] [cursor=pointer]:
            - /url: /saydraft/docs/models/
        - listitem [ref=f10e127]:
          - link "Languages" [ref=f10e128] [cursor=pointer]:
            - /url: /saydraft/docs/languages/
        - listitem [ref=f10e129]:
          - link "Command Mode" [ref=f10e130] [cursor=pointer]:
            - /url: /saydraft/docs/command-mode/
        - listitem [ref=f10e131]:
          - link "Verify offline" [ref=f10e132] [cursor=pointer]:
            - /url: /saydraft/docs/privacy/verify-offline/
        - listitem [ref=f10e133]:
          - link "Troubleshooting" [ref=f10e134] [cursor=pointer]:
            - /url: /saydraft/docs/troubleshooting/
  - contentinfo [ref=f10e135]:
    - link "Saydraft" [ref=f10e136] [cursor=pointer]:
      - /url: /saydraft/
      - text: Saydraft✳
    - paragraph [ref=f10e137]: Your words. Your machine.
    - generic [ref=f10e138]:
      - link "Getting started" [ref=f10e139] [cursor=pointer]:
        - /url: /saydraft/docs/getting-started/
      - link "Languages" [ref=f10e140] [cursor=pointer]:
        - /url: /saydraft/languages/
      - link "Offline dictation guide" [ref=f10e141] [cursor=pointer]:
        - /url: /saydraft/offline-dictation-windows/
      - link "For developers" [ref=f10e142] [cursor=pointer]:
        - /url: /saydraft/dictation-for-developers/
      - link "Privacy" [ref=f10e143] [cursor=pointer]:
        - /url: /saydraft/privacy/
      - link "Credits" [ref=f10e144] [cursor=pointer]:
        - /url: /saydraft/credits/
      - link "Changelog" [ref=f10e145] [cursor=pointer]:
        - /url: /saydraft/changelog/
      - link "MIT license ↗" [ref=f10e146] [cursor=pointer]:
        - /url: https://github.com/tanzir71/saydraft/blob/main/LICENSE
    - navigation "Compare dictation tools" [ref=f10e147]:
      - generic [ref=f10e148]: Compare
      - link "Wispr Flow" [ref=f10e149] [cursor=pointer]:
        - /url: /saydraft/wispr-flow-alternative/
      - link "Typeless" [ref=f10e150] [cursor=pointer]:
        - /url: /saydraft/typeless-alternative/
      - link "Superwhisper" [ref=f10e151] [cursor=pointer]:
        - /url: /saydraft/superwhisper-alternative-windows/
      - link "Windows voice typing" [ref=f10e152] [cursor=pointer]:
        - /url: /saydraft/windows-voice-typing-alternative/
      - link "Dragon" [ref=f10e153] [cursor=pointer]:
        - /url: /saydraft/dragon-alternative/
    - generic [ref=f10e154]:
      - generic [ref=f10e155]: Free, open-source dictation for Windows.
      - navigation "Creator links" [ref=f10e156]:
        - link "Built by tanziro.com" [ref=f10e157] [cursor=pointer]:
          - /url: https://tanziro.com
        - link "Support Saydraft ↗" [ref=f10e158] [cursor=pointer]:
          - /url: https://buymeacoffee.com/tanzir
```

# Test source

```ts
  1   | import { test, expect } from '@playwright/test';
  2   | import { documentationRoutes, resourceRoutes } from '../src/data/documentation';
  3   | import { languages } from '../src/data/languages';
  4   | import { siteOrigin } from '../test-ports';
  5   | 
  6   | test('all documentation and resources are readable, dated and navigable', async ({ page }) => {
  7   |   const external: string[] = [];
  8   |   const errors: string[] = [];
  9   |   page.on('pageerror', (error) => errors.push(error.message));
  10  |   await page.route('**/*', (route) => {
  11  |     if (new URL(route.request().url()).origin !== siteOrigin) { external.push(route.request().url()); return route.abort(); }
  12  |     return route.continue();
  13  |   });
  14  |   for (const { slug } of [...documentationRoutes, ...resourceRoutes]) {
  15  |     await page.goto(`./${slug}/`);
  16  |     await expect(page.locator('.guide-verified time')).toHaveAttribute('datetime', /^\d{4}-\d{2}-\d{2}$/);
  17  |     await expect(page.locator('.guide-sources a').first()).toBeVisible();
> 18  |     expect((await page.locator('.guide-copy').innerText()).length).toBeGreaterThan(500);
      |                                                                    ^ Error: expect(received).toBeGreaterThan(expected)
  19  |     expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  20  |     const contents = page.getByRole('navigation', { name: 'On this page' });
  21  |     for (const href of await contents.locator('a').evaluateAll((links) => links.map((link) => link.getAttribute('href')))) {
  22  |       expect(href).toMatch(/^#/);
  23  |       await expect(page.locator(`[id="${decodeURIComponent(href!.slice(1))}"]`)).toHaveCount(1);
  24  |     }
  25  |     const breadcrumb = (await page.locator('script[type="application/ld+json"]').allTextContents())
  26  |       .map((json) => JSON.parse(json)).find((data) => data['@type'] === 'BreadcrumbList').itemListElement;
  27  |     expect(breadcrumb.at(-1).item).toBe(`https://tanzir71.github.io/saydraft/${slug}/`);
  28  |     if (slug.startsWith('docs')) {
  29  |       const navigation = page.getByRole('navigation', { name: 'Documentation', exact: true });
  30  |       await expect(navigation.locator('a')).toHaveCount(11);
  31  |       await expect(navigation.locator('[aria-current="page"]')).toHaveAttribute('href', `/saydraft/${slug}/`);
  32  |       expect(breadcrumb.length).toBe(slug === 'docs' ? 2 : 3);
  33  |     }
  34  |     if (['docs', 'docs/models', 'docs/privacy/verify-offline', 'download', 'credits'].includes(slug)) {
  35  |       await page.evaluate(async () => { await document.fonts.ready; scrollTo(0, 0); });
  36  |       await page.screenshot({ path: test.info().outputPath(`${slug.replaceAll('/', '-')}.png`), fullPage: true, animations: 'disabled' });
  37  |     }
  38  |   }
  39  |   expect(external).toEqual([]);
  40  |   expect(errors).toEqual([]);
  41  | });
  42  | 
  43  | test('main navigation and documentation contents reach nested offline guidance', async ({ page }) => {
  44  |   await page.goto('./');
  45  |   const menu = page.getByLabel('Navigation menu');
  46  |   if (await menu.isVisible()) await menu.click();
  47  |   await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'Docs', exact: true }).click();
  48  |   await expect(page).toHaveURL(/\/saydraft\/docs\/$/);
  49  |   await page.getByRole('navigation', { name: 'Documentation', exact: true }).getByRole('link', { name: 'Local models' }).click();
  50  |   await expect(page).toHaveURL(/\/docs\/models\/$/);
  51  |   await page.getByRole('navigation', { name: 'Documentation', exact: true }).getByRole('link', { name: 'Verify offline' }).click();
  52  |   const target = page.getByRole('navigation', { name: 'On this page' }).getByRole('link', { name: 'Optional packaged Firewall controls' });
  53  |   await target.focus();
  54  |   await page.keyboard.press('Enter');
  55  |   await expect(page.locator('#optional-packaged-firewall-controls')).toBeInViewport();
  56  |   expect(new URL(page.url()).hash).toBe('#optional-packaged-firewall-controls');
  57  | });
  58  | 
  59  | test('model guidance discloses complete default and optional transfers', async ({ page }) => {
  60  |   for (const path of ['download/', 'docs/models/']) {
  61  |     await page.goto(`./${path}`);
  62  |     await expect(page.locator('[data-model-table="speech"] tbody tr')).toHaveCount(8);
  63  |     const defaultModel = page.locator('[data-model-id="parakeet-tdt-0-6b-v3-int8"]');
  64  |     await expect(defaultModel).toContainText('773.4 MB');
  65  |     await expect(defaultModel).toContainText('CC-BY-4.0 + MIT');
  66  |     const enhancement = page.locator('[data-model-id="gtcrn-speech-enhancement"]');
  67  |     await expect(enhancement).toContainText('0.54 MB');
  68  |     await expect(enhancement).toContainText('MIT');
  69  |   }
  70  |   await expect(page.locator('[data-model-table="editing"] tbody tr')).toHaveCount(5);
  71  |   await expect(page.locator('[data-model-id="qwen35-4b-q4-k-m"]')).toContainText('experimental editing');
  72  |   await page.goto('./docs/languages/');
  73  |   const rows = page.locator('.guide-copy tbody tr');
  74  |   await expect(rows).toHaveCount(19);
  75  |   expect(await rows.locator('th').allTextContents()).toEqual(languages.map((language) => language.name));
  76  |   expect(await rows.locator('code').allTextContents()).toEqual(languages.map((language) => language.code));
  77  |   for (const [index, language] of languages.entries()) {
  78  |     await expect(rows.nth(index).locator('td').last()).toHaveText(language.model === 'default' ? 'Parakeet v3 or All languages' : 'All languages');
  79  |   }
  80  | });
  81  | 
  82  | test('documentation, model tables and original font notices work without JavaScript', async ({ browser }) => {
  83  |   const context = await browser.newContext({ javaScriptEnabled: false, viewport: test.info().project.use.viewport });
  84  |   try {
  85  |     const page = await context.newPage();
  86  |     for (const { slug } of documentationRoutes) {
  87  |       await page.goto(`${siteOrigin}/saydraft/${slug}/`);
  88  |       await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  89  |       await expect(page.locator('.docs-navigation [aria-current="page"]')).toBeVisible();
  90  |       expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  91  |     }
  92  |     await page.goto(`${siteOrigin}/saydraft/docs/models/`);
  93  |     await expect(page.locator('[data-model-table="speech"] tbody tr')).toHaveCount(8);
  94  |     await page.goto(`${siteOrigin}/saydraft/download/`);
  95  |     expect(await page.locator('figure noscript').textContent()).toBe('Select the command text to copy it.');
  96  |     await expect(page.locator('figure noscript')).toBeVisible();
  97  |     await page.goto(`${siteOrigin}/saydraft/credits/`);
  98  |     const notices = page.locator('.guide-copy a[href$="-OFL.txt"]');
  99  |     await expect(notices).toHaveCount(5);
  100 |     for (const href of await notices.evaluateAll((links) => links.map((link) => (link as HTMLAnchorElement).href))) {
  101 |       const response = await context.request.get(href);
  102 |       expect(response.ok()).toBe(true);
  103 |       expect(await response.text()).toContain('SIL OPEN FONT LICENSE');
  104 |     }
  105 |     await page.goto(`${siteOrigin}/saydraft/docs/privacy/verify-offline/`);
  106 |     await expect(page.locator('.guide-copy')).toContainText('separate helpers');
  107 |     await expect(page.locator('.guide-copy')).toContainText('source Python process');
  108 |   } finally { await context.close(); }
  109 | });
  110 | 
```