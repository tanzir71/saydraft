import type { Meta, StoryObj } from "@storybook/react-vite";
import {
  SectionHeader,
  InstrumentPanel,
  FactsSheet,
  HowItWorks,
  ProofSheet,
  FeatureBento,
  SignalPath,
  LanguageWall,
  FinalCTA,
} from "./Landing";
import { installLanding } from "../../scripts/landing";
import "../../styles/home.css";
export default {
  title: "Product/Landing",
  parameters: { fullBleed: true },
} satisfies Meta;
type Story = StoryObj;
export const Instrument: Story = {
  render: () => (
    <div className="container">
      <InstrumentPanel />
    </div>
  ),
  play: () => installLanding(),
};
export const Facts: Story = { render: () => <FactsSheet base="/saydraft/" /> };
export const Steps: Story = {
  render: () => (
    <div className="container landing-v2">
      <HowItWorks />
    </div>
  ),
};
export const Cleanup: Story = {
  render: () => (
    <div className="container landing-v2">
      <ProofSheet />
    </div>
  ),
  play: () => installLanding(),
};
export const Features: Story = {
  render: () => (
    <div className="container landing-v2">
      <FeatureBento />
    </div>
  ),
};
export const PrivacyDiagram: Story = {
  render: () => (
    <div className="container">
      <SignalPath />
    </div>
  ),
  globals: { sheet: "night" },
};
export const Languages: Story = {
  render: () => (
    <div className="container">
      <LanguageWall base="/saydraft/" />
    </div>
  ),
};
export const SectionTitle: Story = {
  render: () => (
    <div className="container landing-v2">
      <SectionHeader
        number="01"
        label="How it works"
        id="story-section-title"
        title="Hold. Talk. Let go."
        description="Saydraft sits in your tray and works in editable Windows apps."
      />
    </div>
  ),
};
export const Final: Story = {
  render: () => (
    <div className="landing-v2">
      <FinalCTA base="/saydraft/" />
    </div>
  ),
};
