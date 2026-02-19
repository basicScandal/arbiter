import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[Arbiter] UI crash caught by ErrorBoundary:", error, info);
  }

  private handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center h-screen bg-void font-mono text-neutral-400 gap-6 p-8">
          <div className="text-event-injection text-sm tracking-[0.3em] uppercase">
            System Fault Detected
          </div>
          <div className="text-xs text-neutral-600 max-w-md text-center leading-relaxed">
            {this.state.error?.message ?? "Unknown rendering error"}
          </div>
          <button
            onClick={this.handleRetry}
            className="mt-4 px-6 py-2 border border-neutral-700 text-neutral-400 text-xs tracking-widest uppercase hover:border-neutral-500 hover:text-neutral-300 transition-colors"
          >
            Retry
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
