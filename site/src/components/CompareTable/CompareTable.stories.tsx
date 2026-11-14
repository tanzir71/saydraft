import type { Meta, StoryObj } from '@storybook/react-vite';
import { CompareTable } from './CompareTable';
import { comparisonRows } from '../storyFixtures';
export default { title: 'Product/CompareTable', component: CompareTable, args: { caption: 'Local speech model setup', products: ['Default speech model', 'All languages model'], rows: comparisonRows } } satisfies Meta<typeof CompareTable>;
type Story = StoryObj<typeof CompareTable>;
export const DatedSources: Story = {};
export const OnDark: Story = { globals: { sheet: 'night' } };
