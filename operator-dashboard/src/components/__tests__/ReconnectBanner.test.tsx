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
    expect(screen.queryByText(/RECONNECTING/)).not.toBeInTheDocument();
  });

  it("does not render during initial connecting", () => {
    useOperatorStore.setState({ connectionState: 'connecting' });
    render(<ReconnectBanner />);
    expect(screen.queryByText(/RECONNECTING/)).not.toBeInTheDocument();
  });

  it("renders when reconnecting", () => {
    useOperatorStore.setState({ connectionState: 'reconnecting' });
    render(<ReconnectBanner />);
    expect(screen.getByText(/RECONNECTING/)).toBeInTheDocument();
  });
});
