/**
 * Backend warm-up as the user sees it.
 *
 * After sign-in the app asks the backend to start its server, load its models and wake the
 * metadata database, which pauses when idle and takes about 15 seconds to resume. The
 * backend reports progress as `status` events; these helpers turn them into display text.
 */
import type { SSEMessage } from "./types";

/** Shown from the moment warm-up is requested until the server answers at all. */
export const STARTING_MESSAGE = "Starting the server";

/** The database pauses after five idle minutes; warm up again a little before that. */
export const REWARM_AFTER_MS = 4 * 60 * 1000;

/** How long a submitted question waits for warm-up before being sent regardless. */
export const WARMUP_WAIT_LIMIT_MS = 30 * 1000;

export interface WarmupProgress {
  /** Text for the status line, or null once there is nothing left to wait for. */
  message: string | null;
  /** The backend finished but something is not available yet. */
  problem: boolean;
}

/** Interpret one event from the warm-up stream. Non-status events leave progress unchanged. */
export function warmupProgress(event: SSEMessage): WarmupProgress | null {
  if (event.event !== "status") return null;
  const stage = String(event.data.stage ?? "");
  const message = String(event.data.message ?? "Warming up");
  if (stage === "ready") return { message: null, problem: false };
  if (stage === "partial") return { message, problem: true };
  return { message, problem: false };
}

/** Whether the backend has been quiet long enough that the database has probably paused. */
export function needsRewarm(lastActivityAt: number, now: number): boolean {
  return now - lastActivityAt >= REWARM_AFTER_MS;
}

/** What the chat shows for a question submitted while warm-up is still running. */
export function waitingForWarmupStage(warmupMessage: string | null): string {
  const doing = warmupMessage ?? STARTING_MESSAGE;
  return `The assistant is still starting up (${doing.charAt(0).toLowerCase()}${doing.slice(1)}). Your question will be sent as soon as it is ready.`;
}
