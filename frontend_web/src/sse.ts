import type { SSEMessage } from "./types";

export class SSEParser {
  private buffer = "";

  push(chunk: string): SSEMessage[] {
    this.buffer += chunk.replace(/\r\n/g, "\n");
    const blocks = this.buffer.split("\n\n");
    this.buffer = blocks.pop() ?? "";
    return blocks.flatMap(parseBlock);
  }

  finish(): SSEMessage[] {
    if (!this.buffer.trim()) return [];
    const messages = parseBlock(this.buffer);
    this.buffer = "";
    return messages;
  }
}

function parseBlock(block: string): SSEMessage[] {
  if (!block || block.startsWith(":")) return [];
  let event = "message";
  const data: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
  }
  if (!data.length) return [];
  try {
    return [{ event, data: JSON.parse(data.join("\n")) as Record<string, unknown> }];
  } catch {
    return [{ event: "error", data: { message: "The server returned an invalid stream event." } }];
  }
}
