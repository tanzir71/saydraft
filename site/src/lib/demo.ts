/** A canned visual simulation. No device, clipboard, model or network APIs. */
export function installDemo() {
  const root = document.querySelector<HTMLElement>('[data-demo-lab]');
  if (!root) return;
  const play = root.querySelector<HTMLButtonElement>('[data-demo-run]')!;
  const reset = root.querySelector<HTMLButtonElement>('[data-demo-reset]')!;
  const controls = root.querySelector<HTMLElement>('[data-demo-controls]')!;
  const bar = root.querySelector<HTMLElement>('[data-bar-demo]')!;
  const label = root.querySelector<HTMLElement>('[data-bar-label]')!;
  const announcement = root.querySelector<HTMLElement>('[data-demo-announcement]')!;
  const outputs = new Map([...root.querySelectorAll<HTMLElement>('[data-clean]')].map((node) => [node, node.textContent!]));
  const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const lifetime = new AbortController();
  let timers: number[] = [];
  function cancelTimers() { for (const timer of timers) window.clearTimeout(timer); timers = []; }
  function activeExample() {
    const choice = root!.querySelector<HTMLInputElement>('input:checked')!.value;
    return [...root!.querySelectorAll<HTMLElement>('[data-sample]')].find((node) => node.dataset.sample === choice)!;
  }
  function setState(state: string, text: string) {
    bar.dataset.state = state; label.textContent = text;
    bar.setAttribute('aria-label', `Saydraft simulation: ${text}`);
  }
  function restore() {
    cancelTimers();
    for (const [node, text] of outputs) node.textContent = text;
    play.disabled = false; setState('idle', 'Ready when you are');
    announcement.textContent = 'Ready. Choose an example to read its prepared draft.';
  }
  function finish() {
    cancelTimers();
    const output = activeExample().querySelector<HTMLElement>('[data-clean]')!;
    output.textContent = outputs.get(output)!;
    setState('inserted', 'Draft ready'); play.disabled = false;
    announcement.textContent = `Example finished. ${output.textContent}`;
  }
  const options = { signal: lifetime.signal };
  play.addEventListener('click', () => {
    if (play.disabled) return;
    cancelTimers(); play.disabled = true;
    activeExample().querySelector<HTMLElement>('[data-clean]')!.textContent = '';
    if (motion.matches) { finish(); return; }
    setState('listening', 'Listening · simulated'); announcement.textContent = 'Playing the prepared example.';
    timers.push(window.setTimeout(() => setState('cleaning', 'Tidying · simulated'), 850));
    timers.push(window.setTimeout(finish, 1550));
  }, options);
  reset.addEventListener('click', () => {
    restore();
    for (const details of root.querySelectorAll('details')) details.open = true;
  }, options);
  for (const input of root.querySelectorAll('input')) input.addEventListener('change', restore, options);
  motion.addEventListener('change', () => { if (motion.matches && play.disabled) finish(); }, options);
  window.addEventListener('pagehide', () => { cancelTimers(); lifetime.abort(); }, { once: true });
  controls.hidden = false;
}
