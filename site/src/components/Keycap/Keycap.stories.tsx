import type { Meta, StoryObj } from "@storybook/react-vite";
import { Keycap } from "./Keycap";
export default {
  title: "Foundations/Keycap",
  component: Keycap,
  args: { legend: "Ctrl" },
} satisfies Meta<typeof Keycap>;
type Story = StoryObj<typeof Keycap>;
export const LightLarge: Story = { args: { size: "L" } };
export const LightMedium: Story = { args: { size: "M" } };
export const LightSmall: Story = {};
export const DarkLarge: Story = {
  args: { size: "L", tone: "dark", legend: "Win" },
};
export const DarkMedium: Story = { args: { size: "M", tone: "dark" } };
export const DarkSmall: Story = { args: { tone: "dark" } };
export const SignalLarge: Story = { args: { size: "L", tone: "signal" } };
export const SignalMedium: Story = { args: { size: "M", tone: "signal" } };
export const SignalSmall: Story = { args: { tone: "signal" } };
