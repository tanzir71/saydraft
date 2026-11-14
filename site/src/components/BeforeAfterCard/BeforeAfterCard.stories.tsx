import type { Meta, StoryObj } from '@storybook/react-vite';
import { BeforeAfterCard } from './BeforeAfterCard';

export default { title: 'Product/BeforeAfterCard', component: BeforeAfterCard, args: { title: 'Change your mind.', before: 'coffee at two actually three', after: 'Coffee at 3.', chip: 'Backtrack: 2 → 3' } } satisfies Meta<typeof BeforeAfterCard>;
export const Backtrack: StoryObj<typeof BeforeAfterCard> = {};
export const Fillers: StoryObj<typeof BeforeAfterCard> = { args: { title: 'Find your rhythm.', before: 'Um, I think, uh, this could work.', after: 'I think this could work.', chip: 'Removed hesitation' } };
export const Lists: StoryObj<typeof BeforeAfterCard> = { args: { title: 'Make a little space.', before: 'First item, send the notes. Second item, book the room.', after: '• Send the notes\n• Book the room', chip: 'Made a list' } };
export const Multilingual: StoryObj<typeof BeforeAfterCard> = { args: { title: 'Keep your language.', before: 'বাংলা ভাষা · العربية', after: 'বাংলা ভাষা · العربية', chip: 'Shared All languages model' } };
