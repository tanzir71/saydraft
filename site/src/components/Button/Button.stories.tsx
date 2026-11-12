import type { Meta, StoryObj } from '@storybook/react-vite';
import { Button } from './Button';

export default { title: 'Foundations/Button', component: Button, args: { children: 'Get Saydraft for Windows', href: '#download' } } satisfies Meta<typeof Button>;
type Story = StoryObj<typeof Button>;
export const Primary: Story = {};
export const Secondary: Story = { args: { variant: 'secondary' } };
export const OnDark: Story = { args: { variant: 'on-dark' }, globals: { sheet: 'night' } };
