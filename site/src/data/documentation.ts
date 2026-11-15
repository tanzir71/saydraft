export const documentationRoutes = [
  { id: 'index', slug: 'docs', name: 'Documentation' },
  { id: 'getting-started', slug: 'docs/getting-started', name: 'Getting started' },
  { id: 'shortcuts', slug: 'docs/shortcuts', name: 'Shortcuts' },
  { id: 'styles', slug: 'docs/styles', name: 'Styles and cleanup' },
  { id: 'dictionary', slug: 'docs/dictionary', name: 'Dictionary' },
  { id: 'models', slug: 'docs/models', name: 'Local models' },
  { id: 'languages', slug: 'docs/languages', name: 'Languages' },
  { id: 'command-mode', slug: 'docs/command-mode', name: 'Command Mode' },
  { id: 'notes', slug: 'docs/notes', name: 'Notes' },
  { id: 'privacy/verify-offline', slug: 'docs/privacy/verify-offline', name: 'Verify offline' },
  { id: 'troubleshooting', slug: 'docs/troubleshooting', name: 'Troubleshooting' },
  { id: 'faq', slug: 'docs/faq', name: 'FAQ' },
] as const;

export const resourceRoutes = [
  { id: 'download', slug: 'download', name: 'Download and setup' },
  { id: 'credits', slug: 'credits', name: 'Credits and licenses' },
  { id: 'privacy', slug: 'privacy', name: 'Privacy' },
] as const;
