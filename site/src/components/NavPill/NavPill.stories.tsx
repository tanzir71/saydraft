import type { Meta, StoryObj } from '@storybook/react-vite';
import { NavPill } from './NavPill';

export default { title: 'Navigation/NavPill', component: NavPill, parameters: { layout: 'fullscreen' } } satisfies Meta<typeof NavPill>;
export const Default: StoryObj<typeof NavPill> = {};
