import type { Meta, StoryObj } from '@storybook/react-vite';
import { Ribbon } from './Ribbon';
export default { title: 'Product/Ribbon', component: Ribbon, args: { text: 'um, let’s meet at two… actually, make that three. just a quick coffee?' } } satisfies Meta<typeof Ribbon>;
type Story = StoryObj<typeof Ribbon>;
export const Animated: Story = {};
export const Static: Story = { args: { animated: false } };
export const ReducedMotion: Story = { globals: { motion: 'reduced' } };
export const OnDark: Story = { globals: { sheet: 'deep' } };
