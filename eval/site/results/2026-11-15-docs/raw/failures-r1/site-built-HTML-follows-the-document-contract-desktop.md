# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: site.spec.ts >> built HTML follows the document contract
- Location: tests\site.spec.ts:259:1

# Error details

```
Error: [
  {
    "filePath": "dist\\docs\\getting-started\\index.html",
    "messages": [
      {
        "ruleId": "valid-id",
        "severity": 2,
        "message": "element id \"1-get-the-app\" must begin with a letter",
        "offset": 10124,
        "line": 4,
        "column": 3020,
        "size": 13,
        "selector": "[id=\"1-get-the-app\"]",
        "ruleUrl": "https://html-validate.org/rules/valid-id.html",
        "context": {
          "kind": 3,
          "id": "1-get-the-app"
        },
        "related": []
      },
      {
        "ruleId": "valid-id",
        "severity": 2,
        "message": "element id \"2-choose-your-microphone\" must begin with a letter",
        "offset": 10392,
        "line": 8,
        "column": 9,
        "size": 24,
        "selector": "[id=\"2-choose-your-microphone\"]",
        "ruleUrl": "https://html-validate.org/rules/valid-id.html",
        "context": {
          "kind": 3,
          "id": "2-choose-your-microphone"
        },
        "related": []
      },
      {
        "ruleId": "valid-id",
        "severity": 2,
        "message": "element id \"3-review-and-install-local-models\" must begin with a letter",
        "offset": 10841,
        "line": 14,
        "column": 9,
        "size": 33,
        "selector": "[id=\"3-review-and-install-local-models\"]",
        "ruleUrl": "https://html-validate.org/rules/valid-id.html",
        "context": {
          "kind": 3,
          "id": "3-review-and-install-local-models"
        },
        "related": []
      },
      {
        "ruleId": "valid-id",
        "severity": 2,
        "message": "element id \"4-choose-a-shortcut-and-practice\" must begin with a letter",
        "offset": 12461,
        "line": 35,
        "column": 9,
        "size": 32,
        "selector": "[id=\"4-choose-a-shortcut-and-practice\"]",
        "ruleUrl": "https://html-validate.org/rules/valid-id.html",
        "context": {
          "kind": 3,
          "id": "4-choose-a-shortcut-and-practice"
        },
        "related": []
      },
      {
        "ruleId": "valid-id",
        "severity": 2,
        "message": "element id \"5-make-it-sound-like-you\" must begin with a letter",
        "offset": 13474,
        "line": 47,
        "column": 9,
        "size": 24,
        "selector": "[id=\"5-make-it-sound-like-you\"]",
        "ruleUrl": "https://html-validate.org/rules/valid-id.html",
        "context": {
          "kind": 3,
          "id": "5-make-it-sound-like-you"
        },
        "related": []
      },
      {
        "ruleId": "valid-id",
        "severity": 2,
        "message": "element id \"6-try-it-offline\" must begin with a letter",
        "offset": 13995,
        "line": 55,
        "column": 9,
        "size": 16,
        "selector": "[id=\"6-try-it-offline\"]",
        "ruleUrl": "https://html-validate.org/rules/valid-id.html",
        "context": {
          "kind": 3,
          "id": "6-try-it-offline"
        },
        "related": []
      }
    ],
    "errorCount": 6,
    "warningCount": 0,
    "fixableErrorCount": 0,
    "fixableWarningCount": 0,
    "source": "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><meta name=\"description\" content=\"Set up local speech models, choose your microphone, try a first dictation and learn Saydraft's Windows shortcuts with a step-by-step walkthrough.\"><meta name=\"theme-color\" content=\"#F5F2E9\"><meta name=\"color-scheme\" content=\"light\"><meta property=\"og:title\" content=\"Getting Started with Saydraft — Offline Dictation Setup\"><meta property=\"og:description\" content=\"Set up local speech models, choose your microphone, try a first dictation and learn Saydraft's Windows shortcuts with a step-by-step walkthrough.\"><meta property=\"og:type\" content=\"website\"><meta property=\"og:url\" content=\"https://tanzir71.github.io/saydraft/docs/getting-started/\"><meta name=\"twitter:card\" content=\"summary\"><link rel=\"canonical\" href=\"https://tanzir71.github.io/saydraft/docs/getting-started/\"><link rel=\"sitemap\" type=\"application/xml\" href=\"/saydraft/sitemap.xml\"><link rel=\"icon\" href=\"/saydraft/favicon.svg?v=2\" type=\"image/svg+xml\"><link rel=\"preload\" as=\"font\" type=\"font/woff2\" href=\"/saydraft/_astro/geist-latin-wght-normal.BgDaEnEv.woff2\" crossorigin=\"anonymous\"><link rel=\"preload\" as=\"font\" type=\"font/woff2\" href=\"/saydraft/_astro/instrument-serif-latin-400-normal.DnYpCC2O.woff2\" crossorigin=\"anonymous\"><link rel=\"preload\" as=\"font\" type=\"font/woff2\" href=\"/saydraft/_astro/instrument-serif-latin-400-italic.DKMiL14s.woff2\" crossorigin=\"anonymous\"><title>Getting Started with Saydraft — Offline Dictation Setup</title><link rel=\"stylesheet\" href=\"/saydraft/_astro/StructuredData.DdusAvpt.css\"><style>._button_1xs8g_1{border-radius:var(--radius-pill);min-height:48px;font:500 15px/1.3 var(--font-body);transition:background var(--motion-fast), transform var(--motion-fast);justify-content:center;align-items:center;gap:24px;padding:14px 24px;text-decoration:none;display:inline-flex}._button_1xs8g_1:hover{transform:translateY(-2px)}._button_1xs8g_1._primary_1xs8g_15{background:var(--color-ink);color:var(--color-paper)}._button_1xs8g_1._primary_1xs8g_15:hover{background:var(--color-deep)}._button_1xs8g_1._secondary_1xs8g_19{background:var(--color-paper-raised);color:var(--color-ink)}._button_1xs8g_1._on-dark_1xs8g_21{background:var(--color-paper);color:var(--color-ink)}._button_1xs8g_1:focus-visible{outline:2px solid var(--color-ink);outline-offset:5px}._button_1xs8g_1._on-dark_1xs8g_21:focus-visible{outline-color:var(--color-paper)}@media (prefers-reduced-motion:reduce){._button_1xs8g_1{transition:none}._button_1xs8g_1:hover{transform:none}}[data-motion=reduced] ._button_1xs8g_1{transition:none;transform:none}._faq_143ht_1{width:100%}._faq_143ht_1 details{border-bottom:1px solid var(--color-hairline)}._faq_143ht_1 summary{justify-content:space-between;align-items:center;gap:24px;padding:25px 0;font-size:18px;list-style:none;display:flex}._faq_143ht_1 summary::-webkit-details-marker{display:none}._faq_143ht_1 summary span{font:26px/1 var(--font-display)}._faq_143ht_1 details[open] summary span{transform:rotate(45deg)}._faq_143ht_1 p{max-width:65ch;color:var(--color-ink-muted);padding:0 36px 25px 0;font-size:15px;line-height:1.7}[data-sheet=night] ._faq_143ht_1 p,[data-sheet=deep] ._faq_143ht_1 p{color:var(--color-on-dark-muted)}\n._code_14z7n_1{border-radius:var(--radius-card);background:var(--color-paper-raised);color:var(--color-ink);margin:28px 0;overflow:hidden}._code_14z7n_1 figcaption{font:12px/1.4 var(--font-mono);flex-wrap:wrap;justify-content:space-between;align-items:center;gap:14px;padding:18px 24px 0;display:flex}._code_14z7n_1 button{background:var(--color-ink);color:var(--color-paper);border-radius:var(--radius-pill);border:0;padding:10px 14px;font-size:12px}._code_14z7n_1 button:focus-visible{outline:2px solid var(--color-ink)}._code_14z7n_1 pre{white-space:pre;margin:0;padding:24px;overflow:auto}._code_14z7n_1 code{font:12px/1.8 var(--font-mono)}._code_14z7n_1 ._feedback_14z7n_13{margin:0;padding-inline:24px;font-size:12px;line-height:1.5}._feedback_14z7n_13:not(:empty){padding-bottom:18px}._code_14z7n_1 noscript{padding:0 24px 18px;font-size:12px;display:block}._callout_14z7n_19{border-radius:var(--radius-card);color:var(--color-ink);margin-block:28px;padding:24px}._info_14z7n_21{background:var(--color-mist)}._warning_14z7n_23{background:var(--color-paper-raised)}._callout_14z7n_19 ._title_14z7n_25{color:var(--color-ink);margin-bottom:10px;font-weight:500}._callout_14z7n_19 div{font-size:14px;line-height:1.65}._toc_14z7n_29{border-block:1px solid var(--color-hairline);padding-block:24px}._toc_14z7n_29>p{font:12px/1.4 var(--font-mono);margin-bottom:16px}._toc_14z7n_29 ol{margin:0;padding-left:22px}._toc_14z7n_29 li{margin-block:10px;font-size:14px;line-height:1.5}._toc_14z7n_29 li[data-depth=\"3\"]{margin-left:20px}.guide-document{max-width:960px}.guide-breadcrumb{color:var(--color-ink-muted);gap:10px;margin-bottom:40px;font-size:12px;display:flex}.guide-breadcrumb span:last-child{text-overflow:ellipsis;white-space:nowrap;overflow:hidden}.guide-document h1{max-width:16ch;font-size:clamp(48px,6vw,80px)}.guide-verified{margin-bottom:44px!important;font-size:12px!important}.guide-copy,.guide-faq,.guide-sources{max-width:72ch}.guide-copy table{table-layout:fixed;border-collapse:collapse;width:100%;margin-block:32px;font-size:13px}.guide-copy th,.guide-copy td{text-align:left;vertical-align:top;border-bottom:1px solid var(--color-hairline);overflow-wrap:anywhere;padding:16px 10px;line-height:1.6}.guide-copy th{font-weight:600}.guide-next{border-radius:var(--radius-card);background:var(--color-paper-raised);margin-block:56px;padding:32px}.guide-next h2{margin-top:0}.guide-related ul{flex-wrap:wrap;gap:12px 24px;padding-left:0;list-style:none;display:flex}.guide-related a{font-size:13px}.guide-sources li{margin-bottom:10px;font-size:13px}.docs-navigation{margin-bottom:32px}.docs-navigation ul{flex-wrap:wrap;gap:8px 20px;margin:0;padding:0;list-style:none;display:flex}.docs-navigation li{margin:0;font-size:13px;line-height:1.6}.docs-navigation a[aria-current=page]{font-weight:600;text-decoration-thickness:2px}.guide-copy pre{max-width:100%}.guide-copy h2{scroll-margin-top:30px}@media (width<=600px){.guide-copy th,.guide-copy td{padding:12px 7px;font-size:12px}.guide-next{padding:24px}}\n.document{max-width:800px;padding-block:80px 96px}.document h1{font-size:var(--type-display-m-size);letter-spacing:-.025em;margin-block:24px 36px;line-height:1.02}.document h2{margin-block:44px 18px;font-size:34px;line-height:1.15}.document p,.document li{color:var(--color-ink-muted);margin-bottom:18px;font-size:16px;line-height:1.75}.document a{color:var(--color-ink)}.document code{font:12px/1.8 var(--font-mono)}.document pre{background:var(--color-paper-raised);border-radius:var(--radius-card);padding:24px;overflow-x:auto}.document ul,.document ol{padding-left:24px}.document .notice{background:var(--color-mist);border-radius:var(--radius-card);color:var(--color-ink);padding:24px}@media (width<=700px){.document{padding-block:54px}.document h1{font-size:48px}}\n</style></head><body><a class=\"skip-link\" href=\"#main\">Skip to content</a><header class=\"_header_1i18w_1\"><nav class=\"_nav_1i18w_3\" aria-label=\"Main navigation\"><a class=\"_wordmark_1i18w_13\" href=\"/saydraft/\" aria-label=\"Saydraft home\">Saydraft<span aria-hidden=\"true\">✳</span></a><div class=\"_links_1i18w_17\"><a href=\"/saydraft/#features\">Features</a><a href=\"/saydraft/languages/\">Languages</a><a href=\"/saydraft/#questions\">Questions</a><a href=\"/saydraft/docs/\">Docs</a><a href=\"https://github.com/tanzir71/saydraft\">GitHub ↗</a></div><a class=\"_download_1i18w_23\" href=\"/saydraft/download/\">Get Saydraft <span aria-hidden=\"true\">↗</span></a><details class=\"_mobile_1i18w_19\"><summary aria-label=\"Navigation menu\"><span aria-hidden=\"true\">☰</span></summary><div><a href=\"/saydraft/#features\">Features</a><a href=\"/saydraft/languages/\">Languages</a><a href=\"/saydraft/#questions\">Questions</a><a href=\"/saydraft/docs/\">Docs</a><a href=\"https://github.com/tanzir71/saydraft\">GitHub ↗</a></div></details></nav></header><main id=\"main\" class=\"document container guide-document\"><nav class=\"guide-breadcrumb\" aria-label=\"Breadcrumb\"><a href=\"/saydraft/\">Saydraft</a><span aria-hidden=\"true\">/</span><a href=\"/saydraft/docs/\">Docs</a><span aria-hidden=\"true\">/</span><span>Your first few words.</span></nav><p class=\"eyebrow\">Getting started</p><h1>Your first <em>few words.</em></h1><p class=\"guide-verified\">Facts checked <time datetime=\"2026-11-14\">2026-11-14</time>. Product plans and features can change.</p><nav class=\"docs-navigation\" aria-label=\"Documentation\"><ul><li><a href=\"/saydraft/docs/\">Documentation</a></li><li><a href=\"/saydraft/docs/getting-started/\" aria-current=\"page\">Getting started</a></li><li><a href=\"/saydraft/docs/shortcuts/\">Shortcuts</a></li><li><a href=\"/saydraft/docs/styles/\">Styles and cleanup</a></li><li><a href=\"/saydraft/docs/dictionary/\">Dictionary</a></li><li><a href=\"/saydraft/docs/models/\">Local models</a></li><li><a href=\"/saydraft/docs/languages/\">Languages</a></li><li><a href=\"/saydraft/docs/command-mode/\">Command Mode</a></li><li><a href=\"/saydraft/docs/privacy/verify-offline/\">Verify offline</a></li><li><a href=\"/saydraft/docs/troubleshooting/\">Troubleshooting</a></li><li><a href=\"/saydraft/docs/faq/\">FAQ</a></li></ul></nav><nav class=\"_toc_14z7n_29\" aria-label=\"On this page\"><p>On this page</p><ol><li data-depth=\"2\"><a href=\"#1-get-the-app\">1. Get the app</a></li><li data-depth=\"2\"><a href=\"#2-choose-your-microphone\">2. Choose your microphone</a></li><li data-depth=\"2\"><a href=\"#3-review-and-install-local-models\">3. Review and install local models</a></li><li data-depth=\"2\"><a href=\"#4-choose-a-shortcut-and-practice\">4. Choose a shortcut and practice</a></li><li data-depth=\"2\"><a href=\"#5-make-it-sound-like-you\">5. Make it sound like you</a></li><li data-depth=\"2\"><a href=\"#6-try-it-offline\">6. Try it offline</a></li><li data-depth=\"2\"><a href=\"#if-something-feels-wrong\">If something feels wrong</a></li></ol></nav><article class=\"guide-copy\"><h2 id=\"1-get-the-app\">1. Get the app</h2>\n<p>Use the current <a href=\"/saydraft/download/\">source instructions</a> on\nWindows 10 or 11. A signed installer and package-manager release are still being\nprepared. First-run setup guides you through the choices below.</p>\n<h2 id=\"2-choose-your-microphone\">2. Choose your microphone</h2>\n<p>On Microphone, keep Default Windows input or choose Refresh inputs to find a\nnamed device. Test input runs a ten-second, level-only check without\ntranscription or saved audio. Check microphone privacy reads Windows permission\nstatus without opening an input. If access is blocked or unknown, follow the\nmicrophone-privacy link to review desktop-app access in Windows settings.</p>\n<h2 id=\"3-review-and-install-local-models\">3. Review and install local models</h2>\n<p>Check this PC gives a provisional capability recommendation. Use speech\nrecommendation selects the suggested speech model; it does not benchmark it,\nenable AI cleanup or download anything.</p>\n<p>Review the download size and licenses, then choose <strong>Download / Resume</strong>.\nProgress shows transfers and checksum verification; Pause is available.\nInstalled packages are checked in the background and reused on later launches.</p>\n<p>After installation, Check model performance measures the selected speech model\nwith bundled audio, without a microphone or download. Preparation is separate\nfrom three timed samples. Stop check waits for native work to finish. Unavailable\nAI cleanup speed stays unmeasured, and a fast sample is not an everyday latency\nguarantee. See <a href=\"/saydraft/docs/models/\">model choices</a>.</p>\n<p>For Thai, Chinese, Korean, Japanese, Hindi, Urdu, Indonesian, Malay, Bengali or\nArabic, add the optional shared All languages model. One download serves those\nlanguages; selecting a language starts no transfer. Portuguese, including Brazil,\nis also covered by the default model. See <a href=\"/saydraft/docs/languages/\">language setup</a>.</p>\n<p>Next requires the selected model to be ready. Catalog packages must pass their\nfile checks. An existing local Whisper directory can instead pass an explicit\noffline performance check while its files remain unchanged. Finish checks the\ncurrent model again before saving. Cancelling setup preserves saved preferences;\ndownloaded files remain separate.</p>\n<h2 id=\"4-choose-a-shortcut-and-practice\">4. Choose a shortcut and practice</h2>\n<p>Existing custom bindings are preserved. A fresh profile uses <strong>Ctrl + Win</strong> to\ndictate, with <strong>F9</strong> as the alternate and <strong>Ctrl + Win + Space</strong> for hands-free.\nLearn shortcut listens while setup stays focused, for up to ten seconds;\nEscape cancels. Manual entry and conflict checks are also available.</p>\n<p>Try it has chat and email fields inside setup. Preparing an installed model opens\nno microphone. Hold your shortcut or choose Record, then release or choose Stop\nand preview. Each practice recording is limited to one minute. Review raw words,\ncleaned text and edit chips. Practice audio stays in memory, creates no History\nentry and uses no external paste or clipboard. You can continue without recording.</p>\n<p>If a stop or Settings change ends practice, choose Prepare practice explicitly\nwhen ready. If setup cannot confirm a stop, cancel and restart Saydraft as prompted.</p>\n<h2 id=\"5-make-it-sound-like-you\">5. Make it sound like you</h2>\n<p>Style quick pick offers Casual or Formal for Messages and Email. Its rules\npreview uses your last practice transcript or a labelled example. Finish saves\nchanged choices and opens Home after practice stops; existing cleanup intensity\nand AI settings stay unchanged.</p>\n<p>Later, use Hub → Style for app-group tones and intensity, Dictionary for names,\nand Snippets for frequently used text. AI cleanup is optional; rules work\nwithout a text model.</p>\n<h2 id=\"6-try-it-offline\">6. Try it offline</h2>\n<p>With compatible speech files installed, open an ordinary text editor and put the\ncursor in an editable field. Hold your shortcut, speak, then release. Disconnect\nWi-Fi and try another sentence. Shift + Alt + Z pastes the last saved dictation.\nReview <a href=\"/saydraft/docs/privacy/verify-offline/\">offline verification</a>\nfor what the check proves and its boundaries.</p>\n<h2 id=\"if-something-feels-wrong\">If something feels wrong</h2>\n<p>Check that the model is installed and the microphone meter responds. Start in a\nnon-elevated text editor; password and protected fields are excluded. History\nkeeps a saved transcript when an app cannot accept insertion. Continue with\n<a href=\"/saydraft/docs/troubleshooting/\">troubleshooting</a> and keep private\naudio or text out of public issue reports.</p></article><section class=\"guide-faq\" aria-labelledby=\"guide-questions\"><h2 id=\"guide-questions\">A few useful answers.</h2><div class=\"_faq_143ht_1\"><details><summary>Can I continue setup without recording?<span aria-hidden=\"true\">+</span></summary><p>Yes. The practice recording is optional. Installed speech files must still be ready, and Finish rechecks the current model before saving.</p></details><details><summary>Does the practice draft paste into another app?<span aria-hidden=\"true\">+</span></summary><p>No. Practice uses chat and email fields inside setup, keeps its audio in memory and creates no History entry or external clipboard/paste action.</p></details></div></section><section class=\"guide-sources\" aria-labelledby=\"guide-sources\"><h2 id=\"guide-sources\">Sources and further reading</h2><ul><li><a href=\"https://github.com/tanzir71/saydraft/blob/main/docs/ONBOARDING.md\">First-run setup, readiness and practice behavior ↗</a></li><li><a href=\"https://github.com/tanzir71/saydraft/blob/main/docs/MICROPHONE.md\">Microphone selection and permission checks ↗</a></li></ul></section><aside class=\"guide-next\"><h2>Try it with your own words.</h2><p>Saydraft is in development and available from source. Review the setup status, model sizes and measured limits before choosing it for your workflow.</p><a class=\"_button_1xs8g_1 _primary_1xs8g_15\" href=\"/saydraft/download/\">Get Saydraft<span aria-hidden=\"true\">↗</span></a></aside><nav class=\"guide-related\" aria-label=\"More guides\"><h2>Keep reading.</h2><ul><li><a href=\"/saydraft/docs/\">Documentation</a></li><li><a href=\"/saydraft/docs/shortcuts/\">Shortcuts</a></li><li><a href=\"/saydraft/docs/styles/\">Styles and cleanup</a></li><li><a href=\"/saydraft/docs/dictionary/\">Dictionary</a></li><li><a href=\"/saydraft/docs/models/\">Local models</a></li><li><a href=\"/saydraft/docs/languages/\">Languages</a></li><li><a href=\"/saydraft/docs/command-mode/\">Command Mode</a></li><li><a href=\"/saydraft/docs/privacy/verify-offline/\">Verify offline</a></li><li><a href=\"/saydraft/docs/troubleshooting/\">Troubleshooting</a></li><li><a href=\"/saydraft/docs/faq/\">FAQ</a></li></ul></nav></main><script type=\"application/ld+json\">{\"@context\":\"https://schema.org\",\"@type\":\"BreadcrumbList\",\"itemListElement\":[{\"@type\":\"ListItem\",\"position\":1,\"name\":\"Saydraft\",\"item\":\"https://tanzir71.github.io/saydraft/\"},{\"@type\":\"ListItem\",\"position\":2,\"name\":\"Docs\",\"item\":\"https://tanzir71.github.io/saydraft/docs/\"},{\"@type\":\"ListItem\",\"position\":3,\"name\":\"Your first few words.\",\"item\":\"https://tanzir71.github.io/saydraft/docs/getting-started/\"}]}</script><script type=\"application/ld+json\">{\"@context\":\"https://schema.org\",\"@type\":\"FAQPage\",\"mainEntity\":[{\"@type\":\"Question\",\"name\":\"Can I continue setup without recording?\",\"acceptedAnswer\":{\"@type\":\"Answer\",\"text\":\"Yes. The practice recording is optional. Installed speech files must still be ready, and Finish rechecks the current model before saving.\"}},{\"@type\":\"Question\",\"name\":\"Does the practice draft paste into another app?\",\"acceptedAnswer\":{\"@type\":\"Answer\",\"text\":\"No. Practice uses chat and email fields inside setup, keeps its audio in memory and creates no History entry or external clipboard/paste action.\"}}]}</script><footer class=\"container site-footer _footer_1kmzv_1\"><a class=\"_mark_1kmzv_3\" href=\"/saydraft/\">Saydraft<span aria-hidden=\"true\">✳</span></a><p class=\"muted\">Your words. Your machine.</p><div class=\"_links_1kmzv_9\"><a href=\"/saydraft/docs/getting-started/\">Getting started</a><a href=\"/saydraft/languages/\">Languages</a><a href=\"/saydraft/offline-dictation-windows/\">Offline dictation guide</a><a href=\"/saydraft/dictation-for-developers/\">For developers</a><a href=\"/saydraft/privacy/\">Privacy</a><a href=\"/saydraft/credits/\">Credits</a><a href=\"/saydraft/changelog/\">Changelog</a><a href=\"https://github.com/tanzir71/saydraft/blob/main/LICENSE\">MIT license ↗</a></div><nav class=\"_compare_1kmzv_13\" aria-label=\"Compare dictation tools\"><span>Compare</span><a href=\"/saydraft/wispr-flow-alternative/\">Wispr Flow</a><a href=\"/saydraft/typeless-alternative/\">Typeless</a><a href=\"/saydraft/superwhisper-alternative-windows/\">Superwhisper</a><a href=\"/saydraft/windows-voice-typing-alternative/\">Windows voice typing</a><a href=\"/saydraft/dragon-alternative/\">Dragon</a></nav><div class=\"_bottom_1kmzv_11\"><small>Free, open-source dictation for Windows.</small><nav aria-label=\"Creator links\"><a href=\"https://tanziro.com\" target=\"_blank\" rel=\"noopener\">Built by tanziro.com</a><a href=\"https://buymeacoffee.com/tanzir\" target=\"_blank\" rel=\"noopener\">Support Saydraft ↗</a></nav></div></footer><script type=\"module\">var e=new WeakSet;function t(t=document){e.has(t)||(e.add(t),t.addEventListener(`click`,async e=>{if(!(e.target instanceof Element))return;let t=e.target.closest(`button[data-copy-text]`);if(!t||t.disabled)return;let n=t.closest(`[data-copy-root]`),r=n?.querySelector(`[data-copy-status]`);if(n&&r){t.disabled=!0;try{if(!navigator.clipboard?.writeText)throw Error(`Clipboard unavailable`);await navigator.clipboard.writeText(t.dataset.copyText??``),n.isConnected&&(r.textContent=`Copied.`)}catch{n.isConnected&&(r.textContent=`Copy unavailable. Select the command text to copy it.`)}finally{t.isConnected&&(t.disabled=!1)}}}))}t();</script></body></html>"
  }
]

expect(received).toBe(expected) // Object.is equality

Expected: true
Received: false
```

# Test source

```ts
  166 |     await expect(page.locator('.language-grid').getByRole('link', { name: `${name} voice typing` })).toHaveAttribute('href', `/saydraft/languages/${slug}/`);
  167 |   }
  168 |   for (const [slug, name, code] of guides) {
  169 |     await page.goto(`./languages/${slug}/`);
  170 |     await expect(page.getByRole('heading', { level: 1 })).toContainText(name);
  171 |     await expect(page.getByRole('heading', { level: 1 })).toContainText('voice typing for Windows.');
  172 |     await expect(page.locator('meta[name="robots"]')).toHaveCount(0);
  173 |     await expect(page.locator('[data-language-native]')).toBeVisible();
  174 |     await expect(page.locator('[data-language-native]')).toHaveAttribute('lang', code === 'pt' ? 'pt-BR' : code);
  175 |     await expect(page.locator('[data-language-native]')).toHaveAttribute('dir', ['ar', 'ur', 'fa'].includes(code) ? 'rtl' : 'ltr');
  176 |     expect((await page.title()).length).toBeLessThanOrEqual(60);
  177 |     const description = await page.locator('meta[name="description"]').getAttribute('content');
  178 |     expect(description!.length).toBeLessThanOrEqual(155);
  179 |     expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  180 |     await expect(page.locator('main code').filter({ hasText: new RegExp(`^${code}$`) })).toBeVisible();
  181 |     const notice = page.locator('.notice');
  182 |     await expect(notice).toContainText(['pt', 'es', 'fr', 'de'].includes(code) ? 'default speech model' : 'shared All languages speech model');
  183 |     await expect(page.getByText('Language selection starts no transfer.', { exact: false })).toBeVisible();
  184 |     const data = (await page.locator('script[type="application/ld+json"]').allTextContents()).map((json) => JSON.parse(json));
  185 |     const document = data.find((item) => item['@type'] === 'WebPage');
  186 |     expect(document.url).toBe(`https://tanzir71.github.io/saydraft/languages/${slug}/`);
  187 |     expect(document.inLanguage).toBe('en');
  188 |     const breadcrumbs = data.find((item) => item['@type'] === 'BreadcrumbList').itemListElement;
  189 |     expect(breadcrumbs.at(-1).item).toBe(document.url);
  190 |     await expect(page.locator('.related-languages a')).toHaveText([
  191 |       ...guides.filter(([other]) => other !== slug).map(([, otherName]) => `${otherName} voice typing`),
  192 |       'All language and model guidance',
  193 |     ]);
  194 |     await page.screenshot({ path: test.info().outputPath(`${slug}.png`), fullPage: true, animations: 'disabled' });
  195 |   }
  196 |   const response = await request.get('./sitemap.xml');
  197 |   expect(response.ok()).toBe(true);
  198 |   expect(response.headers()['content-type']).toMatch(/^(?:application|text)\/xml(?:;|$)/i);
  199 |   const sitemap = await response.text();
  200 |   const urls = [...sitemap.matchAll(/<loc>([^<]+)<\/loc>/g)].map((match) => match[1]);
  201 |   expect(new Set(urls)).toEqual(new Set(publicPages.map((path) => `https://tanzir71.github.io/saydraft/${path}`)));
  202 |   for (const [slug] of guides) expect(urls).toContain(`https://tanzir71.github.io/saydraft/languages/${slug}/`);
  203 |   for (const url of urls) expect((await request.get(new URL(url).pathname)).ok(), url).toBe(true);
  204 | });
  205 | 
  206 | test('content and native questions work with JavaScript disabled', async ({ browser }) => {
  207 |   const context = await browser.newContext({ javaScriptEnabled: false, viewport: test.info().project.use.viewport });
  208 |   const page = await context.newPage();
  209 |   await page.goto(`${siteOrigin}/saydraft/`);
  210 |   await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  211 |   await page.locator('summary').filter({ hasText: 'Is it free?' }).click();
  212 |   await expect(page.getByText('Saydraft is free and open source under the MIT license.', { exact: false })).toBeVisible();
  213 |   await page.getByRole('radio', { name: 'Casual', exact: true }).check();
  214 |   await expect(page.getByText('Can you send the notes when you get a chance?', { exact: true })).toBeVisible();
  215 |   await page.locator('.language-section').getByRole('link', { name: 'Thai voice typing' }).click();
  216 |   await expect(page.getByRole('heading', { level: 1 })).toContainText('Thai');
  217 |   await expect(page.locator('.notice')).toContainText('All languages');
  218 |   await page.goto(`${siteOrigin}/saydraft/download/`);
  219 |   await expect(page.locator('pre code')).toContainText('python -m saydraft');
  220 |   const manualCopy = page.locator('figure noscript');
  221 |   expect(await manualCopy.textContent()).toBe('Select the command text to copy it.');
  222 |   await expect(manualCopy).toBeVisible();
  223 |   await page.goto(`${siteOrigin}/saydraft/offline-dictation-windows/`);
  224 |   const contents = page.getByRole('navigation', { name: 'On this page' });
  225 |   const target = await contents.getByRole('link').first().getAttribute('href');
  226 |   await contents.getByRole('link').first().click();
  227 |   expect(new URL(page.url()).hash).toBe(target);
  228 |   await expect(page.locator(target!)).toBeInViewport();
  229 |   await context.close();
  230 | });
  231 | 
  232 | test('source command copy and guide contents work in the static site', async ({ page }) => {
  233 |   await page.addInitScript(() => {
  234 |     const writes: string[] = [];
  235 |     Object.assign(window, { __sourceCommandCopies: writes });
  236 |     Object.defineProperty(navigator, 'clipboard', { configurable: true, value: {
  237 |       writeText: async (text: string) => { writes.push(text); },
  238 |       readText: () => { throw new Error('Clipboard reads are barred'); },
  239 |     } });
  240 |   });
  241 |   await page.goto('./download/');
  242 |   await page.getByRole('button', { name: 'Copy command', exact: true }).click();
  243 |   await expect(page.getByRole('status')).toHaveText('Copied.');
  244 |   const code = await page.locator('pre code').innerText();
  245 |   expect(await page.evaluate(() => (window as unknown as { __sourceCommandCopies: string[] }).__sourceCommandCopies)).toEqual([code]);
  246 |   await expect(page.getByRole('link', { name: 'Download for Windows', exact: true })).toHaveCount(0);
  247 |   await expect(page.getByText('Storybook fixture only.', { exact: false })).toHaveCount(0);
  248 |   await expect(page.locator('body')).not.toContainText('winget install --id Tanzir.Saydraft');
  249 |   await page.goto('./offline-dictation-windows/');
  250 |   const contents = page.getByRole('navigation', { name: 'On this page' });
  251 |   const links = contents.getByRole('link');
  252 |   expect(await links.count()).toBeGreaterThan(2);
  253 |   const target = await links.first().getAttribute('href');
  254 |   await links.first().click();
  255 |   expect(new URL(page.url()).hash).toBe(target);
  256 |   await expect(page.locator(target!)).toBeInViewport();
  257 | });
  258 | 
  259 | test('built HTML follows the document contract', async () => {
  260 |   const validator = new HtmlValidate(JSON.parse(readFileSync('.htmlvalidate.json', 'utf8')));
  261 |   function htmlFiles(folder: string): string[] {
  262 |     return readdirSync(folder, { withFileTypes: true }).flatMap((item) => item.isDirectory() ? htmlFiles(join(folder, item.name)) : item.name.endsWith('.html') ? [join(folder, item.name)] : []);
  263 |   }
  264 |   for (const file of htmlFiles('dist')) {
  265 |     const report = await validator.validateFile(file);
> 266 |     expect(report.valid, JSON.stringify(report.results, null, 2)).toBe(true);
      |                                                                   ^ Error: [
  267 |   }
  268 | });
  269 | 
  270 | test('navigation fits between tablet and desktop widths', async ({ page }) => {
  271 |   for (const width of [820, 900, 1024]) {
  272 |     await page.setViewportSize({ width, height: 900 });
  273 |     await page.goto('./');
  274 |     expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  275 |     await expect(page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'Get Saydraft' })).toBeVisible();
  276 |   }
  277 | });
  278 | 
```