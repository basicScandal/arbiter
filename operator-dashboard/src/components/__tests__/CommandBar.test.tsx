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

  it("renders START button when idle", () => {
    render(<CommandBar />);
    expect(screen.getByText("START")).toBeInTheDocument();
  });

  it("renders team name input and track dropdown when idle", () => {
    render(<CommandBar />);
    expect(screen.getByPlaceholderText("Team name...")).toBeInTheDocument();
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

  describe("contextual buttons per state", () => {
    it("idle shows only START", () => {
      render(<CommandBar />);
      expect(screen.getByText("START")).toBeInTheDocument();
      expect(screen.queryByText("STOP")).not.toBeInTheDocument();
      expect(screen.queryByText("PAUSE")).not.toBeInTheDocument();
    });

    it("capturing shows STOP and PAUSE", () => {
      useOperatorStore.setState({ demoState: "capturing" });
      render(<CommandBar />);
      expect(screen.getByText("STOP")).toBeInTheDocument();
      expect(screen.getByText("PAUSE")).toBeInTheDocument();
      expect(screen.queryByText("START")).not.toBeInTheDocument();
    });

    it("paused shows RESUME and STOP", () => {
      useOperatorStore.setState({ demoState: "paused" });
      render(<CommandBar />);
      expect(screen.getByText("RESUME")).toBeInTheDocument();
      expect(screen.getByText("STOP")).toBeInTheDocument();
      expect(screen.queryByText("PAUSE")).not.toBeInTheDocument();
    });

    it("stopped shows Q&A, DELIBERATE, RESET", () => {
      useOperatorStore.setState({ demoState: "stopped" });
      render(<CommandBar />);
      expect(screen.getByText("Q&A")).toBeInTheDocument();
      expect(screen.getByText("DELIBERATE")).toBeInTheDocument();
      expect(screen.getByText("RESET")).toBeInTheDocument();
      expect(screen.queryByText("START")).not.toBeInTheDocument();
    });
  });

  describe("button states when idle", () => {
    it("START is disabled when no team name", () => {
      render(<CommandBar />);
      expect(screen.getByText("START")).toBeDisabled();
    });

    it("START is enabled when team name is entered", async () => {
      const user = userEvent.setup();
      render(<CommandBar />);
      await user.type(screen.getByPlaceholderText("Team name..."), "TestTeam");
      expect(screen.getByText("START")).toBeEnabled();
    });
  });

  describe("button states when capturing", () => {
    beforeEach(() => {
      useOperatorStore.setState({ demoState: "capturing" });
    });

    it("STOP is enabled", () => {
      render(<CommandBar />);
      expect(screen.getByText("STOP")).toBeEnabled();
    });

    it("PAUSE is enabled", () => {
      render(<CommandBar />);
      expect(screen.getByText("PAUSE")).toBeEnabled();
    });

    it("team name input is not shown", () => {
      render(<CommandBar />);
      expect(screen.queryByPlaceholderText("Team name...")).not.toBeInTheDocument();
    });

    it("track dropdown is not shown", () => {
      render(<CommandBar />);
      expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
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
  });

  describe("button states when stopped", () => {
    beforeEach(() => {
      useOperatorStore.setState({ demoState: "stopped" });
    });

    it("Q&A is enabled", () => {
      render(<CommandBar />);
      expect(screen.getByText("Q&A")).toBeEnabled();
    });

    it("DELIBERATE is enabled", () => {
      render(<CommandBar />);
      expect(screen.getByText("DELIBERATE")).toBeEnabled();
    });

    it("RESET is enabled", () => {
      render(<CommandBar />);
      expect(screen.getByText("RESET")).toBeEnabled();
    });
  });

  describe("interactions", () => {
    it("calls sendCommand with start, team_name and track on START click", async () => {
      const user = userEvent.setup();
      render(<CommandBar />);
      await user.type(screen.getByPlaceholderText("Team name..."), "AlphaTeam");
      await user.click(screen.getByText("START"));
      expect(mockSendCommand).toHaveBeenCalledWith("start", {
        team_name: "AlphaTeam",
        track: "ROGUE::AGENT",
      });
    });

    it("Enter key triggers start when idle with team name", async () => {
      const user = userEvent.setup();
      render(<CommandBar />);
      const input = screen.getByPlaceholderText("Team name...");
      await user.type(input, "BetaTeam");
      await user.keyboard("{Enter}");
      expect(mockSendCommand).toHaveBeenCalledWith("start", {
        team_name: "BetaTeam",
        track: "ROGUE::AGENT",
      });
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
    it("shows success message", () => {
      useOperatorStore.setState({
        lastCommandResult: { success: true, message: "Demo started" },
      });
      render(<CommandBar />);
      expect(screen.getByText("Demo started")).toBeInTheDocument();
    });

    it("shows failure message", () => {
      useOperatorStore.setState({
        lastCommandResult: { success: false, message: "Error occurred" },
      });
      render(<CommandBar />);
      expect(screen.getByText("Error occurred")).toBeInTheDocument();
    });

    it("does not render message when lastCommandResult is null", () => {
      useOperatorStore.setState({ lastCommandResult: null });
      render(<CommandBar />);
      expect(screen.queryByText("Demo started")).not.toBeInTheDocument();
    });
  });
});
