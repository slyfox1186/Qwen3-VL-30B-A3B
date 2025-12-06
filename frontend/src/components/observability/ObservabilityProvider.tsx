"use client";

import { useEffect, useRef } from "react";
import {
  initObservability,
  captureError,
  handleBoundaryError,
} from "@/lib/observability";
import "./ObservabilityProvider.css";

interface ObservabilityProviderProps {
  children: React.ReactNode;
  sentryDsn?: string;
}

/**
 * Provider component that initializes observability on mount.
 *
 * Wraps children with error boundary for catching React errors.
 */
export function ObservabilityProvider({
  children,
  sentryDsn,
}: ObservabilityProviderProps) {
  const initialized = useRef(false);

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;

    // Initialize observability
    initObservability({
      sentryDsn,
      environment: process.env.NODE_ENV,
      debug: process.env.NODE_ENV === "development",
      enablePerformance: true,
    });

    // Global error handlers
    const handleError = (event: ErrorEvent) => {
      captureError(event.error || new Error(event.message), {
        component: "global",
        action: "error",
      });
    };

    const handleUnhandledRejection = (event: PromiseRejectionEvent) => {
      const error =
        event.reason instanceof Error
          ? event.reason
          : new Error(String(event.reason));
      captureError(error, {
        component: "global",
        action: "unhandledRejection",
      });
    };

    window.addEventListener("error", handleError);
    window.addEventListener("unhandledrejection", handleUnhandledRejection);

    return () => {
      window.removeEventListener("error", handleError);
      window.removeEventListener("unhandledrejection", handleUnhandledRejection);
    };
  }, [sentryDsn]);

  return <ErrorBoundary>{children}</ErrorBoundary>;
}

/**
 * Error boundary for catching React rendering errors.
 */
interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  ErrorBoundaryState
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void {
    handleBoundaryError(error, {
      componentStack: errorInfo.componentStack || "",
    });
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-boundary-container">
          <div className="error-boundary-content">
            <div className="error-boundary-icon">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
            </div>
            <h2 className="error-boundary-title">Something went wrong</h2>
            <p className="error-boundary-message">
              {this.state.error?.message || "An unexpected error occurred"}
            </p>
            <div className="error-boundary-actions">
              <button
                onClick={this.handleReset}
                className="error-boundary-button"
              >
                Try Again
              </button>
              <button
                onClick={() => window.location.reload()}
                className="error-boundary-button error-boundary-button-secondary"
              >
                Reload Page
              </button>
            </div>
            {process.env.NODE_ENV === "development" && this.state.error && (
              <pre className="error-boundary-stack">
                {this.state.error.stack}
              </pre>
            )}
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

// Need React for class component
import React from "react";

export default ObservabilityProvider;
