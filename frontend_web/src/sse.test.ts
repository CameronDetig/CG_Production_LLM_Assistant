import { describe, expect, it } from "vitest";
import { SSEParser } from "./sse";

describe("SSEParser", () => {
  it("parses events split across arbitrary chunks and ignores heartbeats", () => {
    const parser = new SSEParser();
    expect(parser.push("event: answer_chunk\nda")).toEqual([]);
    expect(parser.push('ta: {"text":"hel')).toEqual([]);
    expect(parser.push('lo"}\n\n: heartbeat\n\nevent: done\ndata: {"failed":false}\n\n')).toEqual([
      { event: "answer_chunk", data: { text: "hello" } },
      { event: "done", data: { failed: false } },
    ]);
  });

  it("turns malformed JSON into a safe error event", () => {
    const parser = new SSEParser();
    expect(parser.push("event: status\ndata: nope\n\n")[0].event).toBe("error");
  });
});
