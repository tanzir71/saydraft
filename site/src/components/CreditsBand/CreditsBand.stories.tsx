import type { Meta, StoryObj } from '@storybook/react-vite';
import { CreditsBand } from './CreditsBand';
export default { title: 'Layout/CreditsBand', component: CreditsBand, parameters: { fullBleed: true }, args: { href: '/saydraft/credits/' } } satisfies Meta<typeof CreditsBand>;
type Story = StoryObj<typeof CreditsBand>;
export const OpenModels: Story = {};
