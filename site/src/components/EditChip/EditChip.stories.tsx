import type { Meta, StoryObj } from '@storybook/react-vite';
import { EditChip } from './EditChip';
export default { title: 'Product/EditChip', component: EditChip, args: { children: 'Backtrack: 2 → 3' } } satisfies Meta<typeof EditChip>;
type Story = StoryObj<typeof EditChip>;
export const Backtrack: Story = {};
export const Filler: Story = { args: { children: 'Removed hesitation' } };
export const OnDark: Story = { globals: { sheet: 'night' } };
