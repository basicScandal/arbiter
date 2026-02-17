import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { Header } from "../Header";
import { useOperatorStore } from "../../store/operatorStore";

describe("Header", () => {
  beforeEach(() => {
    useOperatorStore.setState({
      connected: true,
      demoState: "idle",
    });
  });

  it("renders ARBITER title", () => {
    render(<Header />);
    expect(screen.getByText("ARBITER")).toBeInTheDocument();
  });

  it("shows STANDBY label when idle", () => {
    render(<Header />);
    expect(screen.getByText("STANDBY")).toBeInTheDocument();
  });

  it("shows CAPTURING label when capturing", () => {
    useOperatorStore.setState({ demoState: "capturing" });
    render(<Header />);
    expect(screen.getByText("CAPTURING")).toBeInTheDocument();
  });

  it("shows PAUSED label when paused", () => {
    useOperatorStore.setState({ demoState: "paused" });
    render(<Header />);
    expect(screen.getByText("PAUSED")).toBeInTheDocument();
  });

  it("shows ANALYSIS COMPLETE label when stopped", () => {
    useOperatorStore.setState({ demoState: "stopped" });
    render(<Header />);
    expect(screen.getByText("ANALYSIS COMPLETE")).toBeInTheDocument();
  });

  it("renders StateIndicator for idle", () => {
    render(<Header />);
    const indicator = document.querySelector('div[title="State: idle"]');
    expect(indicator).toBeInTheDocument();
  });

  it("renders StateIndicator for capturing", () => {
    useOperatorStore.setState({ demoState: "capturing" });
    render(<Header />);
    const indicator = document.querySelector('div[title="State: capturing"]');
    expect(indicator).toBeInTheDocument();
  });

  it("renders StateIndicator for paused", () => {
    useOperatorStore.setState({ demoState: "paused" });
    render(<Header />);
    const indicator = document.querySelector('div[title="State: paused"]');
    expect(indicator).toBeInTheDocument();
  });

  it("renders StateIndicator for stopped", () => {
    useOperatorStore.setState({ demoState: "stopped" });
    render(<Header />);
    const indicator = document.querySelector('div[title="State: stopped"]');
    expect(indicator).toBeInTheDocument();
  });
});
