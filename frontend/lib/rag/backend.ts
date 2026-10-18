import "server-only";
import type { RagStreamEvent } from "./types";

export type { RagSource, RagStage, RagStreamEvent } from "./types";

const DEFAULT_TIMEOUT_MS = 15_000;

/**
 * Resolves the FastAPI backend base URL. Render's `fromService` injects a bare
 * host (no scheme), so a missing scheme is filled in here.
 */
export function getBackendUrl(): string | null {
  const raw = process.env.BACKEND_API_URL?.trim();
  if (!raw) {
    return null;
  }
  const withScheme = /^https?:\/\//.test(raw)
    ? raw
    : `${raw.startsWith("localhost") || raw.startsWith("127.") ? "http" : "https"}://${raw}`;
  return withScheme.replace(/\/+$/, "");
}

export class BackendError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

/**
 * Server-side fetch against the backend with the shared API key attached.
 * `timeoutMs` bounds the wait for response headers only, so a long streamed
 * answer is not cut off once the backend has started responding.
 */
export async function backendFetch(
  path: string,
  init: RequestInit & { timeoutMs?: number } = {}
): Promise<Response> {
  const base = getBackendUrl();
  if (!base) {
    throw new BackendError(
      "BACKEND_API_URL is not configured on the frontend.",
      503
    );
  }

  const { timeoutMs = DEFAULT_TIMEOUT_MS, headers, signal, ...rest } = init;
  const timeout = new AbortController();
  const timer = setTimeout(
    () => timeout.abort(new DOMException("Timed out", "TimeoutError")),
    timeoutMs
  );

  try {
    return await fetch(`${base}${path}`, {
      ...rest,
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        ...(process.env.BACKEND_API_KEY && {
          "X-API-Key": process.env.BACKEND_API_KEY,
        }),
        ...headers,
      },
      signal: signal
        ? AbortSignal.any([signal, timeout.signal])
        : timeout.signal,
    });
  } catch (error) {
    if (timeout.signal.aborted) {
      throw new BackendError(
        "The knowledge backend did not respond in time. It may be waking up — try again in a moment.",
        504
      );
    }
    throw new BackendError(
      "Could not reach the knowledge backend. Check BACKEND_API_URL and that the service is running.",
      502
    );
  } finally {
    clearTimeout(timer);
  }
}

/** Extracts FastAPI's `detail` (string or validation array) into readable text. */
export async function readBackendError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") {
      return body.detail;
    }
    if (Array.isArray(body?.detail)) {
      return body.detail
        .map((d: { msg?: string }) => d.msg)
        .filter(Boolean)
        .join("; ");
    }
  } catch {
    /* non-JSON body */
  }
  if (response.status === 401) {
    return "The backend rejected the API key. Make sure BACKEND_API_KEY matches on both services.";
  }
  return `Backend responded with ${response.status}`;
}

/** Parses the backend's `data: {...}\n\n` SSE stream into typed events. */
export async function* parseRagStream(
  body: ReadableStream<Uint8Array>
): AsyncGenerator<RagStreamEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });

    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const frame = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      boundary = buffer.indexOf("\n\n");

      const data = frame
        .split("\n")
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trimStart())
        .join("\n");
      if (!data) {
        continue;
      }
      try {
        yield JSON.parse(data) as RagStreamEvent;
      } catch {
        /* ignore malformed frame */
      }
    }
  }
}
