import { Component, type ReactNode } from 'react';
import { routeHref } from '../navigation';

type Props = { children: ReactNode };
type State = { error: Error | null };

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div className="errorBoundaryShell">
          <div className="errorBoundaryCard">
            <div className="errorBoundaryIcon">⚠</div>
            <div className="errorBoundaryTitle">Something went wrong</div>
            <div className="errorBoundaryMessage">{this.state.error.message}</div>
            <div className="errorBoundaryActions">
              <button
                className="btnPrimary"
                onClick={() => {
                  this.setState({ error: null });
                  window.location.hash = '#/';
                }}
              >
                Back to Dashboard
              </button>
              <button
                className="compactButton"
                onClick={() => window.location.reload()}
              >
                Reload page
              </button>
            </div>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
