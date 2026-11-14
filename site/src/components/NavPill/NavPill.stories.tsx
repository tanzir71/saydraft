import type { Meta, StoryObj } from '@storybook/react-vite';
import { NavPill } from './NavPill';

export default { title: 'Navigation/NavPill', component: NavPill, parameters: { fullBleed: true } } satisfies Meta<typeof NavPill>;
export const Default: StoryObj<typeof NavPill> = {};
export const MobileMenuOpen: StoryObj<typeof NavPill> = { args: { menuOpen: true } };
