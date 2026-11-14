import type { Meta, StoryObj } from '@storybook/react-vite';
import { Eyebrow } from './Eyebrow';
export default { title: 'Foundations/Eyebrow', component: Eyebrow, args: { children: 'Offline dictation for Windows' } } satisfies Meta<typeof Eyebrow>;
type Story = StoryObj<typeof Eyebrow>;
export const Paper: Story = {};
export const OnDark: Story = { globals: { sheet: 'night' } };
