import type { Preview } from '@storybook/react-vite';
import '../src/styles/global.css';
import { installCopyButtons } from '../src/scripts/copy';

if (typeof document !== 'undefined') installCopyButtons();

const preview: Preview = {
  parameters: { layout: 'fullscreen' },
  globalTypes: {
    sheet: { description: 'Sheet background', toolbar: { icon: 'circlehollow', items: ['paper', 'night', 'deep'] } },
    motion: { description: 'Reduced motion', toolbar: { icon: 'play', items: ['full', 'reduced'] } },
  },
  initialGlobals: { sheet: 'paper', motion: 'full' },
  decorators: [(Story, context) => <div data-sheet={context.globals.sheet} data-motion={context.globals.motion}
    style={{ padding: context.parameters.fullBleed ? 0 : 'clamp(24px, 5vw, 64px)', minHeight: '100vh' }}><Story /></div>],
};
export default preview;
