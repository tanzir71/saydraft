import type { Meta, StoryObj } from '@storybook/react-vite';
import { Footer } from './Footer';
export default { title: 'Layout/Footer', component: Footer, parameters: { fullBleed: true } } satisfies Meta<typeof Footer>;
type Story = StoryObj<typeof Footer>;
export const ProjectAndCreator: Story = {};
