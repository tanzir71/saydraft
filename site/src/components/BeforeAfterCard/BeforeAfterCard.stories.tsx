import type { Meta, StoryObj } from '@storybook/react-vite';
import { BeforeAfterCard } from './BeforeAfterCard';

export default { title: 'Product/BeforeAfterCard', component: BeforeAfterCard, args: { title: 'Change your mind.', before: 'coffee at two actually three', after: 'Coffee at 3.', chip: 'Backtrack: 2 → 3' } } satisfies Meta<typeof BeforeAfterCard>;
export const Backtrack: StoryObj<typeof BeforeAfterCard> = {};
export const Multilingual: StoryObj<typeof BeforeAfterCard> = { args: { title: 'Keep your language.', before: 'বাংলা ভাষা · العربية', after: 'বাংলা ভাষা · العربية', chip: 'Shared All languages model' } };
