const installed = new WeakSet<Document>();

/** Only a deliberate click writes the requested public command. Never reads clipboard data. */
export function installCopyButtons(root: Document = document) {
  if (installed.has(root)) return;
  installed.add(root);
  root.addEventListener('click', async (event) => {
    if (!(event.target instanceof Element)) return;
    const button = event.target.closest<HTMLButtonElement>('button[data-copy-text]');
    if (!button || button.disabled) return;
    const container = button.closest<HTMLElement>('[data-copy-root]');
    const status = container?.querySelector<HTMLElement>('[data-copy-status]');
    if (!container || !status) return;
    button.disabled = true;
    try {
      if (!navigator.clipboard?.writeText) throw new Error('Clipboard unavailable');
      await navigator.clipboard.writeText(button.dataset.copyText ?? '');
      if (container.isConnected) status.textContent = 'Copied.';
    } catch {
      if (container.isConnected) status.textContent = 'Copy unavailable. Select the command text to copy it.';
    } finally {
      if (button.isConnected) button.disabled = false;
    }
  });
}
