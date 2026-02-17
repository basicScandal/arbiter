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

  it("renders ARBITER OPERATOR title", () => {
    render(<Header />);
    expect(screen.getByText("ARBITER OPERATOR")).toBeInTheDocument();
  });

  it("shows current demoState text", () => {
    render(<Header />);
    expect(screen.getByText("idle")).toBeInTheDocument();
  });

  it("shows capturing state text", () => {
    useOperatorStore.setState({ demoState: "capturing" });
    render(<Header />);
    expect(screen.getByText("capturing")).toBeInTheDocument();
  });

  it("shows paused state text", () => {
    useOperatorStore.setState({ demoState: "paused" });
    render(<Header />);
    expect(screen.getByText("paused")).toBeInTheDocument();
  });

  it("shows stopped state text", () => {
    useOperatorStore.setState({ demoState: "stopped" });
    render(<Header />);
    expect(screen.getByText("stopped")).toBeInTheDocument();
  });

  it("renders StateIndicator with correct color for idle", () => {
    render(<Header />);
    const indicator = document.querySelector('span[title="State: idle"]');
    expect(indicator).toBeInTheDocument();
    expect(indicator?.className).toContain("bg-arbiter-green");
  });

  it("renders StateIndicator with correct color for capturing", () => {
    useOperatorStore.setState({ demoState: "capturing" });
    render(<Header />);
    const indicator = document.querySelector('span[title="State: capturing"]');
    expect(indicator).toBeInTheDocument();
    expect(indicator?.className).toContain("bg-arbiter-cyan");
  });

  it("renders StateIndicator with correct color for paused", () => {
    useOperatorStore.setState({ demoState: "paused" });
    render(<Header />);
    const indicator = document.querySelector('span[title="State: paused"]');
    expect(indicator).toBeInTheDocument();
    expect(indicator?.className).toContain("bg-arbiter-yellow");
  });

  it("renders StateIndicator with correct color for stopped", () => {
    useOperatorStore.setState({ demoState: "stopped" });
    render(<Header />);
    const indicator = document.querySelector('span[title="State: stopped"]');
    expect(indicator).toBeInTheDocument();
    expect(indicator?.className).toContain("bg-arbiter-red");
  });
});
