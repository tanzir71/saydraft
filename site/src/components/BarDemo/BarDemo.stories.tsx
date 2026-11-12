import type { Meta, StoryObj } from '@storybook/react-vite';
import { BarDemo } from './BarDemo';

export default { title: 'Product/BarDemo', component: BarDemo } satisfies Meta<typeof BarDemo>;
type Story = StoryObj<typeof BarDemo>;
export const Listening: Story = { args: { state: 'listening' } };
export const Idle: Story = { args: { state: 'idle' } };
export const Cleaning: Story = { args: { state: 'cleaning' } };
export const Inserted: Story = { args: { state: 'inserted' } };
export const ReducedMotion: Story = { globals: { motion: 'reduced' } };
