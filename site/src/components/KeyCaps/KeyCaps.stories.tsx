import type { Meta, StoryObj } from '@storybook/react-vite';
import { KeyCaps } from './KeyCaps';
export default { title: 'Foundations/KeyCaps', component: KeyCaps, args: { keys: ['Ctrl', 'Win'] } } satisfies Meta<typeof KeyCaps>;
type Story = StoryObj<typeof KeyCaps>;
export const HoldToSpeak: Story = {};
export const HandsFree: Story = { args: { keys: ['Ctrl', 'Win', 'Space'] } };
export const PasteLast: Story = { args: { keys: ['Shift', 'Alt', 'Z'] } };
export const OnDark: Story = { globals: { sheet: 'deep' } };
