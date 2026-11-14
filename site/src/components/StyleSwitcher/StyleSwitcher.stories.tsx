import type { Meta, StoryObj } from '@storybook/react-vite';
import { StyleSwitcher } from './StyleSwitcher';
import { sentences } from '../storyFixtures';
export default { title: 'Product/StyleSwitcher', component: StyleSwitcher, args: { sentences } } satisfies Meta<typeof StyleSwitcher>;
type Story = StoryObj<typeof StyleSwitcher>;
export const Formal: Story = {};
export const Casual: Story = { args: { initialTone: 'casual' } };
export const VeryCasual: Story = { args: { initialTone: 'very-casual' } };
export const IndependentInstances: Story = { render: () => <><StyleSwitcher sentences={sentences} /><StyleSwitcher sentences={sentences} initialTone="casual" /></> };
