import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { ReconnectBanner } from "../ReconnectBanner";
import { useOperatorStore } from "../../store/operatorStore";

describe("ReconnectBanner", () => {
  beforeEach(() => {
    useOperatorStore.setState({ connectionState: 'connected' });
  });

  it("does not render when connected", () => {
    render(<ReconnectBanner />);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("renders during initial connecting", () => {
    useOperatorStore.setState({ connectionState: 'connecting' });
    render(<ReconnectBanner />);
    expect(screen.getByText(/CONNECTING\.\.\./)).toBeInTheDocument();
  });

  it("renders when reconnecting", () => {
    useOperatorStore.setState({ connectionState: 'reconnecting' });
    render(<ReconnectBanner />);
    expect(screen.getByText(/RECONNECTING/)).toBeInTheDocument();
  });

  it("shows different messages for connecting vs reconnecting", () => {
    useOperatorStore.setState({ connectionState: 'connecting' });
    const { rerender } = render(<ReconnectBanner />);
    expect(screen.getByText("CONNECTING...")).toBeInTheDocument();

    useOperatorStore.setState({ connectionState: 'reconnecting' });
    rerender(<ReconnectBanner />);
    expect(screen.getByText(/CONNECTION LOST/)).toBeInTheDocument();
  });
});
