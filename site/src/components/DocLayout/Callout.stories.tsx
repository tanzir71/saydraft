import type { Meta, StoryObj } from '@storybook/react-vite';
import { Callout } from './Callout';
export default { title: 'Docs/Callout', component: Callout, args: { title: 'Set up once', children: 'Review the model size and license, then start its download. Installed files are reused offline.' } } satisfies Meta<typeof Callout>;
type Story = StoryObj<typeof Callout>;
export const Information: Story = {};
export const Warning: Story = { args: { variant: 'warning', title: 'Still in development', children: 'Owner accuracy and release latency are separate acceptance gates.' } };
export const OnDark: Story = { globals: { sheet: 'night' } };
