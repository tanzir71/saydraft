import type { Meta, StoryObj } from '@storybook/react-vite';
import { StatBlock } from './StatBlock';
export default { title: 'Product/StatBlock', component: StatBlock, args: { value: 'Local.', label: 'Your words stay on your PC.', detail: 'A qualitative statement, not a speed benchmark.' } } satisfies Meta<typeof StatBlock>;
type Story = StoryObj<typeof StatBlock>;
export const Qualitative: Story = {};
export const Sourced: Story = { args: { value: 'MIT', label: 'Free and open source.', detail: 'Models have separate licenses.', source: { href: 'https://github.com/tanzir71/saydraft/blob/main/LICENSE', label: 'App license' }, verified: '2026-11-15' } };
export const OnDark: Story = { globals: { sheet: 'night' } };
