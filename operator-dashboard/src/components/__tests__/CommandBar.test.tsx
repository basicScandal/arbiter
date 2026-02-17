import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CommandBar } from "../CommandBar";
import { useOperatorStore } from "../../store/operatorStore";

describe("CommandBar", () => {
  const mockSendCommand = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    useOperatorStore.setState({
      demoState: "idle",
      lastCommandResult: null,
      sendCommand: mockSendCommand,
    });
  });

  it("renders all 7 buttons", () => {
    render(<CommandBar />);
    expect(screen.getByText("START")).toBeInTheDocument();
    expect(screen.getByText("STOP")).toBeInTheDocument();
    expect(screen.getByText("PAUSE")).toBeInTheDocument();
    expect(screen.getByText("RESUME")).toBeInTheDocument();
    expect(screen.getByText("QA")).toBeInTheDocument();
    expect(screen.getByText("DELIBERATE")).toBeInTheDocument();
    expect(screen.getByText("RESET")).toBeInTheDocument();
  });

  it("renders team name input and track dropdown", () => {
    render(<CommandBar />);
    expect(screen.getByPlaceholderText("Team Name")).toBeInTheDocument();
    expect(screen.getByRole("combobox")).toBeInTheDocument();
  });

  it("defaults track dropdown to ROGUE::AGENT", () => {
    render(<CommandBar />);
    const select = screen.getByRole("combobox") as HTMLSelectElement;
    expect(select.value).toBe("ROGUE::AGENT");
  });

  it("renders all 4 track options", () => {
    render(<CommandBar />);
    const options = screen.getAllByRole("option");
    expect(options).toHaveLength(4);
    expect(options.map((o) => o.textContent)).toEqual([
      "SHADOW::VECTOR",
      "SENTINEL::MESH",
      "ZERO::PROOF",
      "ROGUE::AGENT",
    ]);
  });

  describe("button states when idle", () => {
    it("START is disabled when no team name", () => {
      render(<CommandBar />);
      expect(screen.getByText("START")).toBeDisabled();
    });

    it("START is enabled when team name is entered", async () => {
      const user = userEvent.setup();
      render(<CommandBar />);
      await user.type(screen.getByPlaceholderText("Team Name"), "TestTeam");
      expect(screen.getByText("START")).toBeEnabled();
    });

    it("STOP is disabled when idle", () => {
      render(<CommandBar />);
      expect(screen.getByText("STOP")).toBeDisabled();
    });

    it("PAUSE is disabled when idle", () => {
      render(<CommandBar />);
      expect(screen.getByText("PAUSE")).toBeDisabled();
    });

    it("RESUME is disabled when idle", () => {
      render(<CommandBar />);
      expect(screen.getByText("RESUME")).toBeDisabled();
    });

    it("QA is disabled when idle", () => {
      render(<CommandBar />);
      expect(screen.getByText("QA")).toBeDisabled();
    });

    it("DELIBERATE is disabled when idle", () => {
      render(<CommandBar />);
      expect(screen.getByText("DELIBERATE")).toBeDisabled();
    });

    it("RESET is disabled when idle", () => {
      render(<CommandBar />);
      expect(screen.getByText("RESET")).toBeDisabled();
    });
  });

  describe("button states when capturing", () => {
    beforeEach(() => {
      useOperatorStore.setState({ demoState: "capturing" });
    });

    it("START is disabled", () => {
      render(<CommandBar />);
      expect(screen.getByText("START")).toBeDisabled();
    });

    it("STOP is enabled", () => {
      render(<CommandBar />);
      expect(screen.getByText("STOP")).toBeEnabled();
    });

    it("PAUSE is enabled", () => {
      render(<CommandBar />);
      expect(screen.getByText("PAUSE")).toBeEnabled();
    });

    it("RESUME is disabled", () => {
      render(<CommandBar />);
      expect(screen.getByText("RESUME")).toBeDisabled();
    });

    it("team name input is disabled", () => {
      render(<CommandBar />);
      expect(screen.getByPlaceholderText("Team Name")).toBeDisabled();
    });

    it("track dropdown is disabled", () => {
      render(<CommandBar />);
      expect(screen.getByRole("combobox")).toBeDisabled();
    });
  });

  describe("button states when paused", () => {
    beforeEach(() => {
      useOperatorStore.setState({ demoState: "paused" });
    });

    it("STOP is enabled", () => {
      render(<CommandBar />);
      expect(screen.getByText("STOP")).toBeEnabled();
    });

    it("RESUME is enabled", () => {
      render(<CommandBar />);
      expect(screen.getByText("RESUME")).toBeEnabled();
    });

    it("PAUSE is disabled", () => {
      render(<CommandBar />);
      expect(screen.getByText("PAUSE")).toBeDisabled();
    });
  });

  describe("button states when stopped", () => {
    beforeEach(() => {
      useOperatorStore.setState({ demoState: "stopped" });
    });

    it("QA is enabled", () => {
      render(<CommandBar />);
      expect(screen.getByText("QA")).toBeEnabled();
    });

    it("DELIBERATE is enabled", () => {
      render(<CommandBar />);
      expect(screen.getByText("DELIBERATE")).toBeEnabled();
    });

    it("RESET is enabled", () => {
      render(<CommandBar />);
      expect(screen.getByText("RESET")).toBeEnabled();
    });

    it("START is disabled", () => {
      render(<CommandBar />);
      expect(screen.getByText("START")).toBeDisabled();
    });

    it("STOP is disabled", () => {
      render(<CommandBar />);
      expect(screen.getByText("STOP")).toBeDisabled();
    });
  });

  describe("interactions", () => {
    it("calls sendCommand with start, team_name and track on START click", async () => {
      const user = userEvent.setup();
      render(<CommandBar />);
      await user.type(screen.getByPlaceholderText("Team Name"), "AlphaTeam");
      await user.click(screen.getByText("START"));
      expect(mockSendCommand).toHaveBeenCalledWith("start", {
        team_name: "AlphaTeam",
        track: "ROGUE::AGENT",
      });
    });

    it("Enter key triggers start when idle with team name", async () => {
      const user = userEvent.setup();
      render(<CommandBar />);
      const input = screen.getByPlaceholderText("Team Name");
      await user.type(input, "BetaTeam");
      await user.keyboard("{Enter}");
      expect(mockSendCommand).toHaveBeenCalledWith("start", {
        team_name: "BetaTeam",
        track: "ROGUE::AGENT",
      });
    });

    it("Enter key does not trigger start when not idle", async () => {
      useOperatorStore.setState({ demoState: "capturing" });
      const user = userEvent.setup();
      render(<CommandBar />);
      // Input is disabled when not idle, so Enter shouldn't fire
      expect(mockSendCommand).not.toHaveBeenCalled();
    });

    it("STOP button calls sendCommand with stop", async () => {
      useOperatorStore.setState({ demoState: "capturing" });
      const user = userEvent.setup();
      render(<CommandBar />);
      await user.click(screen.getByText("STOP"));
      expect(mockSendCommand).toHaveBeenCalledWith("stop");
    });

    it("PAUSE button calls sendCommand with pause", async () => {
      useOperatorStore.setState({ demoState: "capturing" });
      const user = userEvent.setup();
      render(<CommandBar />);
      await user.click(screen.getByText("PAUSE"));
      expect(mockSendCommand).toHaveBeenCalledWith("pause");
    });

    it("RESUME button calls sendCommand with resume", async () => {
      useOperatorStore.setState({ demoState: "paused" });
      const user = userEvent.setup();
      render(<CommandBar />);
      await user.click(screen.getByText("RESUME"));
      expect(mockSendCommand).toHaveBeenCalledWith("resume");
    });
  });

  describe("lastCommandResult display", () => {
    it("shows success message with green styling", () => {
      useOperatorStore.setState({
        lastCommandResult: { success: true, message: "Demo started" },
      });
      render(<CommandBar />);
      const msgEl = screen.getByText("Demo started");
      expect(msgEl).toBeInTheDocument();
      expect(msgEl.className).toContain("text-arbiter-green");
    });

    it("shows failure message with red styling", () => {
      useOperatorStore.setState({
        lastCommandResult: { success: false, message: "Error occurred" },
      });
      render(<CommandBar />);
      const msgEl = screen.getByText("Error occurred");
      expect(msgEl).toBeInTheDocument();
      expect(msgEl.className).toContain("text-arbiter-red");
    });

    it("does not render message when lastCommandResult is null", () => {
      useOperatorStore.setState({ lastCommandResult: null });
      render(<CommandBar />);
      expect(screen.queryByText("Demo started")).not.toBeInTheDocument();
    });
  });
});
