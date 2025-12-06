/**
 * Frontend observability utilities.
 *
 * Provides:
 * - Sentry error tracking integration
 * - Performance monitoring
 * - Custom event logging
 * - Request timing utilities
 */

// ============================================================================
// Types
// ============================================================================

interface ErrorContext {
  component?: string;
  action?: string;
  sessionId?: string;
  [key: string]: unknown;
}

interface PerformanceEntry {
  name: string;
  duration: number;
  startTime: number;
  metadata?: Record<string, unknown>;
}

interface ObservabilityConfig {
  sentryDsn?: string;
  environment?: string;
  debug?: boolean;
  enablePerformance?: boolean;
}

// ============================================================================
// Configuration
// ============================================================================

let isInitialized = false;
let config: ObservabilityConfig = {
  environment: process.env.NODE_ENV || "development",
  debug: process.env.NODE_ENV === "development",
  enablePerformance: true,
};

// Sentry instance (dynamically imported)
let Sentry: typeof import("@sentry/nextjs") | null = null;

// ============================================================================
// Initialization
// ============================================================================

/**
 * Initialize observability with optional Sentry integration.
 *
 * @param options - Configuration options
 */
export async function initObservability(
  options: ObservabilityConfig = {}
): Promise<void> {
  if (isInitialized) {
    return;
  }

  config = { ...config, ...options };

  // Initialize Sentry if DSN provided
  if (config.sentryDsn) {
    try {
      Sentry = await import("@sentry/nextjs");
      Sentry.init({
        dsn: config.sentryDsn,
        environment: config.environment,
        tracesSampleRate: config.environment === "production" ? 0.1 : 1.0,
        debug: config.debug,
        // Capture unhandled rejections
        integrations: [
          Sentry.replayIntegration({
            maskAllText: true,
            blockAllMedia: true,
          }),
        ],
        replaysSessionSampleRate: 0.1,
        replaysOnErrorSampleRate: 1.0,
      });

      if (config.debug) {
        console.log("[Observability] Sentry initialized");
      }
    } catch (error) {
      console.warn("[Observability] Failed to initialize Sentry:", error);
    }
  }

  isInitialized = true;

  if (config.debug) {
    console.log("[Observability] Initialized with config:", {
      environment: config.environment,
      sentryEnabled: !!config.sentryDsn,
      performanceEnabled: config.enablePerformance,
    });
  }
}

// ============================================================================
// Error Tracking
// ============================================================================

/**
 * Capture an error with optional context.
 *
 * @param error - The error to capture
 * @param context - Additional context
 */
export function captureError(
  error: Error | string,
  context?: ErrorContext
): void {
  const errorObj = typeof error === "string" ? new Error(error) : error;

  // Log to console in development
  if (config.debug) {
    console.error("[Observability] Error captured:", errorObj, context);
  }

  // Send to Sentry
  if (Sentry) {
    const sentryInstance = Sentry;
    sentryInstance.withScope((scope: { setExtra: (k: string, v: unknown) => void; setTag: (k: string, v: string) => void }) => {
      if (context) {
        Object.entries(context).forEach(([key, value]) => {
          scope.setExtra(key, value);
        });

        if (context.component) {
          scope.setTag("component", context.component);
        }

        if (context.action) {
          scope.setTag("action", context.action);
        }

        if (context.sessionId) {
          scope.setTag("sessionId", context.sessionId);
        }
      }

      sentryInstance.captureException(errorObj);
    });
  }
}

/**
 * Capture a message/event with optional context.
 *
 * @param message - The message to capture
 * @param level - Severity level
 * @param context - Additional context
 */
export function captureMessage(
  message: string,
  level: "info" | "warning" | "error" = "info",
  context?: ErrorContext
): void {
  if (config.debug) {
    const logFn = level === "error" ? console.error : level === "warning" ? console.warn : console.log;
    logFn(`[Observability] ${level}:`, message, context);
  }

  if (Sentry) {
    const sentryInstance = Sentry;
    sentryInstance.withScope((scope: { setExtra: (k: string, v: unknown) => void }) => {
      if (context) {
        Object.entries(context).forEach(([key, value]) => {
          scope.setExtra(key, value);
        });
      }
      sentryInstance.captureMessage(message, level);
    });
  }
}

// ============================================================================
// Performance Monitoring
// ============================================================================

const performanceMarks = new Map<string, number>();
const performanceEntries: PerformanceEntry[] = [];

/**
 * Start a performance measurement.
 *
 * @param name - Unique name for this measurement
 */
export function startMeasure(name: string): void {
  if (!config.enablePerformance) return;

  performanceMarks.set(name, performance.now());

  if (config.debug) {
    console.log(`[Observability] Performance: Started "${name}"`);
  }
}

/**
 * End a performance measurement and record it.
 *
 * @param name - Name matching the startMeasure call
 * @param metadata - Optional metadata to attach
 * @returns Duration in milliseconds, or -1 if not found
 */
export function endMeasure(
  name: string,
  metadata?: Record<string, unknown>
): number {
  if (!config.enablePerformance) return -1;

  const startTime = performanceMarks.get(name);
  if (startTime === undefined) {
    console.warn(`[Observability] No start mark found for "${name}"`);
    return -1;
  }

  const endTime = performance.now();
  const duration = endTime - startTime;

  performanceMarks.delete(name);

  const entry: PerformanceEntry = {
    name,
    duration,
    startTime,
    metadata,
  };

  performanceEntries.push(entry);

  // Keep only last 100 entries
  if (performanceEntries.length > 100) {
    performanceEntries.shift();
  }

  if (config.debug) {
    console.log(
      `[Observability] Performance: "${name}" took ${duration.toFixed(2)}ms`,
      metadata
    );
  }

  // Report to Sentry if very slow
  if (Sentry && duration > 5000) {
    Sentry.addBreadcrumb({
      category: "performance",
      message: `Slow operation: ${name}`,
      data: { duration, ...metadata },
      level: "warning",
    });
  }

  return duration;
}

/**
 * Measure an async function's execution time.
 *
 * @param name - Name for this measurement
 * @param fn - Async function to measure
 * @param metadata - Optional metadata
 * @returns Result of the function
 */
export async function measureAsync<T>(
  name: string,
  fn: () => Promise<T>,
  metadata?: Record<string, unknown>
): Promise<T> {
  startMeasure(name);
  try {
    const result = await fn();
    endMeasure(name, { ...metadata, success: true });
    return result;
  } catch (error) {
    endMeasure(name, { ...metadata, success: false, error: String(error) });
    throw error;
  }
}

/**
 * Get recent performance entries.
 *
 * @param count - Number of entries to return
 * @returns Recent performance entries
 */
export function getPerformanceEntries(count = 10): PerformanceEntry[] {
  return performanceEntries.slice(-count);
}

// ============================================================================
// User Context
// ============================================================================

/**
 * Set user context for error tracking.
 *
 * @param userId - User identifier
 * @param userData - Additional user data
 */
export function setUser(
  userId: string,
  userData?: Record<string, string>
): void {
  if (Sentry) {
    Sentry.setUser({
      id: userId,
      ...userData,
    });
  }

  if (config.debug) {
    console.log("[Observability] User set:", userId);
  }
}

/**
 * Clear user context.
 */
export function clearUser(): void {
  if (Sentry) {
    Sentry.setUser(null);
  }

  if (config.debug) {
    console.log("[Observability] User cleared");
  }
}

// ============================================================================
// Breadcrumbs
// ============================================================================

/**
 * Add a breadcrumb for debugging context.
 *
 * @param category - Category of the breadcrumb
 * @param message - Description
 * @param data - Additional data
 */
export function addBreadcrumb(
  category: string,
  message: string,
  data?: Record<string, unknown>
): void {
  if (Sentry) {
    Sentry.addBreadcrumb({
      category,
      message,
      data,
      level: "info",
    });
  }

  if (config.debug) {
    console.log(`[Observability] Breadcrumb [${category}]:`, message, data);
  }
}

// ============================================================================
// Chat-specific Helpers
// ============================================================================

/**
 * Track chat message sent.
 */
export function trackMessageSent(sessionId: string, hasImages: boolean): void {
  addBreadcrumb("chat", "Message sent", {
    sessionId,
    hasImages,
  });
}

/**
 * Track streaming started.
 */
export function trackStreamingStarted(sessionId: string): void {
  startMeasure(`streaming:${sessionId}`);
  addBreadcrumb("chat", "Streaming started", { sessionId });
}

/**
 * Track streaming completed.
 */
export function trackStreamingCompleted(
  sessionId: string,
  tokenCount?: number
): void {
  const duration = endMeasure(`streaming:${sessionId}`, { tokenCount });
  addBreadcrumb("chat", "Streaming completed", {
    sessionId,
    duration,
    tokenCount,
  });
}

/**
 * Track streaming error.
 */
export function trackStreamingError(sessionId: string, error: string): void {
  endMeasure(`streaming:${sessionId}`, { error });
  captureError(new Error(error), {
    component: "chat",
    action: "streaming",
    sessionId,
  });
}

// ============================================================================
// React Error Boundary Helper
// ============================================================================

/**
 * Error boundary fallback component props.
 */
export interface ErrorFallbackProps {
  error: Error;
  resetError: () => void;
}

/**
 * Handle error boundary errors.
 *
 * @param error - The caught error
 * @param errorInfo - React error info
 */
export function handleBoundaryError(
  error: Error,
  errorInfo: { componentStack: string }
): void {
  captureError(error, {
    component: "ErrorBoundary",
    componentStack: errorInfo.componentStack,
  });
}

// ============================================================================
// Export Types
// ============================================================================

export type { ErrorContext, PerformanceEntry, ObservabilityConfig };
