import type { Meta, StoryObj } from '@storybook/react-vite';
import { CodeBlock } from './CodeBlock';
export default { title: 'Docs/CodeBlock', component: CodeBlock, args: { code: 'py -3.13 -m venv .venv\n.venv\\Scripts\\python -m pip install -r requirements.txt\n.venv\\Scripts\\python -m saydraft' } } satisfies Meta<typeof CodeBlock>;
type Story = StoryObj<typeof CodeBlock>;
export const Commands: Story = {};
export const LongLine: Story = { args: { code: 'Get-FileHash .\\Saydraft-0.1.0-win-x64.zip -Algorithm SHA256 | Format-List -Property Algorithm,Hash,Path' } };
export const OnDark: Story = { globals: { sheet: 'deep' } };
