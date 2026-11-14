import type { Meta, StoryObj } from '@storybook/react-vite';
import { AnnouncementBar } from './AnnouncementBar';
export default { title: 'Layout/AnnouncementBar', component: AnnouncementBar, parameters: { fullBleed: true }, args: { children: 'Saydraft is in development. Explore the current source.', href: 'https://github.com/tanzir71/saydraft' } } satisfies Meta<typeof AnnouncementBar>;
type Story = StoryObj<typeof AnnouncementBar>;
export const Linked: Story = {};
export const TextOnly: Story = { args: { href: undefined, children: 'Free and open source. Speech and cleanup run on your PC.' } };
