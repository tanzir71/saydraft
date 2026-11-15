import type { Meta, StoryObj } from "@storybook/react-vite";
import { Mark } from "./Mark";
export default { title: "Foundations/Mark", component: Mark } satisfies Meta<
  typeof Mark
>;
type Story = StoryObj<typeof Mark>;
export const Signal: Story = {};
