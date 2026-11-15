import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { Thinking } from "../../frontend_web/src/Thinking";

afterEach(cleanup);

describe("Thinking", () => {
  it("shows the current stage reported by the backend", () => {
    render(<Thinking stage="Writing a database query" />);
    expect(screen.getByRole("status")).toHaveTextContent("Writing a database query");
  });

  it("falls back to a generic label before the first status event", () => {
    render(<Thinking />);
    expect(screen.getByRole("status")).toHaveTextContent("Working");
  });
});
