import type { Meta, StoryObj } from '@storybook/react-vite';
import { DownloadCard } from './DownloadCard';
import { exampleRelease } from '../storyFixtures';
export default { title: 'Product/DownloadCard', component: DownloadCard } satisfies Meta<typeof DownloadCard>;
type Story = StoryObj<typeof DownloadCard>;
export const Development: Story = {};
export const FutureReleaseFixture: Story = { args: { release: exampleRelease } };
export const WithoutPackageManager: Story = { args: { release: { ...exampleRelease, packageCommand: undefined } } };
export const OnDark: Story = { globals: { sheet: 'night' } };
