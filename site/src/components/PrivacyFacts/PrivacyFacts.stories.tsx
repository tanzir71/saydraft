import type { Meta, StoryObj } from '@storybook/react-vite';
import { PrivacyFacts } from './PrivacyFacts';
export default { title: 'Product/PrivacyFacts', component: PrivacyFacts } satisfies Meta<typeof PrivacyFacts>;
type Story = StoryObj<typeof PrivacyFacts>;
export const Paper: Story = {};
export const OnDark: Story = { globals: { sheet: 'night' } };
