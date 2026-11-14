import type { Meta, StoryObj } from '@storybook/react-vite';
import { TableOfContents } from './TableOfContents';
export default { title: 'Docs/TableOfContents', component: TableOfContents, args: { headings: [{ id: 'setup', text: 'Set up your speech model' }, { id: 'languages', text: 'Choose your languages', depth: 3 }, { id: 'offline', text: 'Go offline' }] } } satisfies Meta<typeof TableOfContents>;
type Story = StoryObj<typeof TableOfContents>;
export const Sections: Story = {};
export const OnDark: Story = { globals: { sheet: 'deep' } };
