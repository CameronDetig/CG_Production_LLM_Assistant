import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { Thinking } from "../../frontend_web/src/Thinking";
import {
  REWARM_AFTER_MS,
  STARTING_MESSAGE,
  needsRewarm,
  waitingForWarmupStage,
  warmupProgress,
} from "../../frontend_web/src/warmup";

const status = (stage: string, message: string) => ({ event: "status", data: { stage, message } });

describe("backend warm-up status", () => {
  afterEach(cleanup);

  it("shows each stage the backend reports until it is ready", () => {
    expect(warmupProgress(status("server_ready", "Server is up"))).toEqual({ message: "Server is up", problem: false });
    expect(warmupProgress(status("warming", "Waking the database"))).toEqual({ message: "Waking the database", problem: false });
    expect(warmupProgress(status("ready", "Ready"))).toEqual({ message: null, problem: false });
  });

  it("flags a backend that finished without everything available", () => {
    expect(warmupProgress(status("partial", "The database is not responding yet")))
      .toEqual({ message: "The database is not responding yet", problem: true });
  });

  it("ignores events that are not status updates", () => {
    expect(warmupProgress({ event: "done", data: {} })).toBeNull();
  });

  it("warms up again only after the database has had time to pause", () => {
    const now = 1_000_000_000;
    expect(needsRewarm(now - REWARM_AFTER_MS + 1000, now)).toBe(false);
    expect(needsRewarm(now - REWARM_AFTER_MS, now)).toBe(true);
    // Nothing has reached the backend yet in this tab.
    expect(needsRewarm(0, now)).toBe(true);
  });

  it("tells a user who asked during warm-up what is happening, in the chat itself", () => {
    const stage = waitingForWarmupStage("Waking the database");
    expect(stage).toContain("still starting up");
    expect(stage).toContain("waking the database");
    expect(stage).toContain("will be sent");

    render(<Thinking stage={stage} />);
    expect(screen.getByRole("status")).toHaveTextContent("The assistant is still starting up (waking the database)");
  });

  it("falls back to the server starting when no progress has arrived yet", () => {
    expect(waitingForWarmupStage(null)).toContain(STARTING_MESSAGE.toLowerCase());
  });
});
