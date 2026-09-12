import { freshSession } from "./auth";
import { SSEParser } from "./sse";
import type { ConversationSummary, Message, RuntimeConfig, SSEMessage } from "./types";

const EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855";

async function hexSha256(body: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(body));
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function authenticatedFetch(
  config: RuntimeConfig,
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const session = await freshSession(config);
  if (!session) throw new Error("SESSION_EXPIRED");
  const body = typeof init.body === "string" ? init.body : "";
  const headers = new Headers(init.headers);
  headers.set("X-Cognito-Token", session.idToken);
  headers.set("X-Amz-Content-Sha256", body ? await hexSha256(body) : EMPTY_SHA256);
  if (body) headers.set("Content-Type", "application/json");
  const response = await fetch(path, { ...init, headers });
  if (response.status === 401) throw new Error("SESSION_EXPIRED");
  return response;
}

export async function listConversations(config: RuntimeConfig): Promise<ConversationSummary[]> {
  const response = await authenticatedFetch(config, "/api/conversations");
  if (!response.ok) throw new Error("Unable to load conversations");
  return ((await response.json()) as { conversations: ConversationSummary[] }).conversations;
}

export async function getConversation(config: RuntimeConfig, id: string): Promise<Message[]> {
  const response = await authenticatedFetch(config, `/api/conversations/${encodeURIComponent(id)}`);
  if (!response.ok) throw new Error("Unable to load conversation");
  const data = (await response.json()) as { conversation: { messages: Message[] } };
  return data.conversation.messages;
}

export async function deleteConversation(config: RuntimeConfig, id: string): Promise<void> {
  const response = await authenticatedFetch(config, `/api/conversations/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
  if (!response.ok) throw new Error("Unable to delete conversation");
}

export async function streamChat(
  config: RuntimeConfig,
  payload: Record<string, unknown>,
  onEvent: (message: SSEMessage) => void,
  signal?: AbortSignal,
): Promise<void> {
  const body = JSON.stringify(payload);
  const response = await authenticatedFetch(config, "/api/chat", { method: "POST", body, signal });
  if (!response.ok || !response.body) throw new Error(`Chat request failed (${response.status})`);
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const parser = new SSEParser();
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    parser.push(decoder.decode(value, { stream: true })).forEach(onEvent);
  }
  parser.push(decoder.decode()).concat(parser.finish()).forEach(onEvent);
}

export async function imageToBase64(file: File): Promise<{ data: string; preview: string }> {
  const bitmap = await createImageBitmap(file);
  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 512;
  const context = canvas.getContext("2d");
  if (!context) throw new Error("Image processing is unavailable");
  context.fillStyle = "#000";
  context.fillRect(0, 0, 512, 512);
  const scale = Math.min(512 / bitmap.width, 512 / bitmap.height);
  const width = bitmap.width * scale;
  const height = bitmap.height * scale;
  context.drawImage(bitmap, (512 - width) / 2, (512 - height) / 2, width, height);
  bitmap.close();
  const preview = canvas.toDataURL("image/jpeg", 0.85);
  return { data: preview.split(",")[1], preview };
}
