import type { Meta, StoryObj } from '@storybook/react-vite';
import { CreditsBand } from './CreditsBand';
export default { title: 'Layout/CreditsBand', component: CreditsBand, parameters: { fullBleed: true }, args: { href: '/saydraft/credits/' } } satisfies Meta<typeof CreditsBand>;
type Story = StoryObj<typeof CreditsBand>;
export const OpenModels: Story = {};
export const WithStars: Story = { args: { stars: { count: 42, checked: '2026-11-14' } } };
export const ZeroStars: Story = { args: { stars: { count: 0, checked: '2026-11-14' } } };
