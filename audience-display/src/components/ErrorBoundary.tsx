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
    console.error("[Arbiter] Display crash caught by ErrorBoundary:", error, info);
  }

  private handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center h-screen bg-arbiter-bg font-mono text-neutral-400 gap-6 p-8">
          <div className="text-arbiter-red text-lg tracking-[0.3em] uppercase">
            Display Fault
          </div>
          <div className="text-sm text-neutral-600 max-w-lg text-center leading-relaxed">
            {this.state.error?.message ?? "Unknown rendering error"}
          </div>
          <button
            onClick={this.handleRetry}
            className="mt-4 px-8 py-3 border border-neutral-700 text-neutral-400 text-sm tracking-widest uppercase hover:border-neutral-500 hover:text-neutral-300 transition-colors"
          >
            Retry
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
