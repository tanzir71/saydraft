import type { Meta, StoryObj } from '@storybook/react-vite';
import { SerifHeading } from './SerifHeading';
export default { title: 'Foundations/SerifHeading', component: SerifHeading, args: { children: <>Your words. <em>Your machine.</em></> } } satisfies Meta<typeof SerifHeading>;
type Story = StoryObj<typeof SerifHeading>;
export const Medium: Story = {};
export const Large: Story = { args: { size: 'large' } };
export const Hero: Story = { args: { as: 'h1', size: 'xl' } };
export const OnDark: Story = { globals: { sheet: 'deep' } };
