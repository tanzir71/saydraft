import type { Meta, StoryObj } from '@storybook/react-vite';
import { FAQ } from './FAQ';

export default { title: 'Content/FAQ', component: FAQ, args: { questions: [{ question: 'Does it work without Wi-Fi?', answer: 'Yes. Download the models during setup, then dictate offline.' }, { question: 'Is Saydraft free?', answer: 'The app is open source under the MIT license. Model licenses are listed separately.' }] } } satisfies Meta<typeof FAQ>;
export const Closed: StoryObj<typeof FAQ> = {};
export const Open: StoryObj<typeof FAQ> = { args: { openFirst: true } };
