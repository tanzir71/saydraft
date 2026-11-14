function port(name: string, fallback: number) {
  const value = Number(process.env[name] ?? fallback);
  if (!Number.isInteger(value) || value < 1024 || value > 65535) throw new Error(`Invalid local test port: ${name}`);
  return value;
}
export const sitePort = port('SAYDRAFT_TEST_PORT', 4173);
export const siteOrigin = `http://127.0.0.1:${sitePort}`;
export const storybookPort = port('SAYDRAFT_STORYBOOK_PORT', 6006);
export const storybookOrigin = `http://127.0.0.1:${storybookPort}`;
