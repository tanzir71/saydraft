/** Canned public examples only. No media, clipboard, storage or network APIs. */
export function installLanding() {
  const scene = document.querySelector<HTMLElement>("[data-demo-scene]");
  const play = scene?.querySelector<HTMLButtonElement>("[data-demo-play]");
  const bar = scene?.querySelector<HTMLElement>("[data-bar-demo]");
  const label = scene?.querySelector<HTMLElement>("[data-bar-label]");
  const meta = scene?.querySelector<HTMLElement>("[data-bar-meta]");
  const status = scene?.querySelector<HTMLElement>("[data-demo-status]");
  const result = scene?.querySelector<HTMLElement>("[data-demo-result]");
  const preference = window.matchMedia("(prefers-reduced-motion: reduce)");
  let playbackId = 0;
  const reduced = () =>
    preference.matches ||
    document.documentElement.dataset.motion === "reduced" ||
    Boolean(scene?.closest('[data-motion="reduced"]'));
  function setState(state: string, text: string, detail: string) {
    if (!bar || !label || !meta || !result) return;
    bar.dataset.state = state;
    bar.setAttribute("aria-label", `Saydraft example: ${text}`);
    label.textContent = text;
    meta.textContent = detail;
    result.style.opacity = state === "inserted" ? "1" : ".35";
    if (state !== "inserted") delete result.dataset.typing;
  }
  function finish() {
    setState("inserted", "Words, delivered", "✓");
    if (result) {
      if (!reduced()) result.dataset.typing = "true";
      else delete result.dataset.typing;
    }
    if (status)
      status.textContent =
        "Example finished. Let’s meet at 3. Just a quick coffee?";
  }
  async function run() {
    if (!play || play.disabled) return;
    const currentPlayback = ++playbackId;
    play.disabled = true;
    if (!reduced()) {
      setState("listening", "Listening", "00:07");
      await new Promise((resolve) => window.setTimeout(resolve, 1100));
      if (currentPlayback !== playbackId) return;
      if (!reduced()) {
        setState("cleaning", "Tidying your words", "LOCAL");
        await new Promise((resolve) => window.setTimeout(resolve, 600));
        if (currentPlayback !== playbackId) return;
      }
    }
    finish();
    play.disabled = false;
  }
  play?.addEventListener("click", run);
  preference.addEventListener("change", () => {
    if (reduced()) {
      playbackId++;
      finish();
      if (play) play.disabled = false;
    }
  });
  if (reduced()) finish();
  else if (scene) {
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          observer.disconnect();
          void run();
        }
      },
      { threshold: 0.35 },
    );
    observer.observe(scene);
  }

  for (const proof of document.querySelectorAll<HTMLElement>(
    "[data-cleanup-proof]",
  )) {
    const tabs = [...proof.querySelectorAll<HTMLButtonElement>('[role="tab"]')];
    const panels = [
      ...proof.querySelectorAll<HTMLElement>('[role="tabpanel"]'),
    ];
    const activate = (index: number) => {
      tabs.forEach((tab, i) => {
        tab.setAttribute("aria-selected", String(i === index));
        tab.tabIndex = i === index ? 0 : -1;
      });
      panels.forEach((panel, i) => {
        panel.setAttribute("aria-hidden", String(i !== index));
        if (i === index) panel.tabIndex = 0;
        else panel.removeAttribute("tabindex");
      });
    };
    const horizontal = window.matchMedia("(max-width: 700px)");
    const orientation = () =>
      proof
        .querySelector('[role="tablist"]')
        ?.setAttribute(
          "aria-orientation",
          horizontal.matches ? "horizontal" : "vertical",
        );
    orientation();
    horizontal.addEventListener("change", orientation);
    tabs.forEach((tab, index) => {
      tab.addEventListener("click", () => activate(index));
      tab.addEventListener("keydown", (event) => {
        const previous = horizontal.matches ? "ArrowLeft" : "ArrowUp";
        const next = horizontal.matches ? "ArrowRight" : "ArrowDown";
        let target: number;
        if (event.key === previous)
          target = (index + tabs.length - 1) % tabs.length;
        else if (event.key === next) target = (index + 1) % tabs.length;
        else if (event.key === "Home") target = 0;
        else if (event.key === "End") target = tabs.length - 1;
        else return;
        event.preventDefault();
        activate(target);
        tabs[target].focus();
      });
    });
  }
}
