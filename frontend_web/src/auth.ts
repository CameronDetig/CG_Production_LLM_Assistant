import type { RuntimeConfig, Session } from "./types";

const SESSION_KEY = "cg-assistant.session";
const FLOW_KEY = "cg-assistant.oauth-flow";

function base64Url(bytes: Uint8Array): string {
  let binary = "";
  bytes.forEach((byte) => (binary += String.fromCharCode(byte)));
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function randomValue(): string {
  return base64Url(crypto.getRandomValues(new Uint8Array(32)));
}

async function sha256(value: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return base64Url(new Uint8Array(digest));
}

function decodePayload(token: string): Record<string, unknown> {
  const encoded = token.split(".")[1];
  if (!encoded) throw new Error("Invalid identity token");
  const padded = encoded.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(encoded.length / 4) * 4, "=");
  return JSON.parse(atob(padded)) as Record<string, unknown>;
}

export async function loadConfig(): Promise<RuntimeConfig> {
  const response = await fetch("/config.json", { cache: "no-store" });
  if (!response.ok) throw new Error("Unable to load site configuration");
  const config = (await response.json()) as RuntimeConfig;
  if (!config.cognitoDomain || !config.cognitoClientId) {
    throw new Error("Cognito has not been configured for this deployment");
  }
  return config;
}

export async function createAuthorizationRequest(config: RuntimeConfig): Promise<string> {
  const verifier = randomValue();
  const state = randomValue();
  const nonce = randomValue();
  sessionStorage.setItem(FLOW_KEY, JSON.stringify({ verifier, state, nonce }));
  const params = new URLSearchParams({
    response_type: "code",
    client_id: config.cognitoClientId,
    redirect_uri: `${window.location.origin}/auth/callback`,
    scope: config.oauthScopes.join(" "),
    code_challenge: await sha256(verifier),
    code_challenge_method: "S256",
    state,
    nonce,
  });
  return `https://${config.cognitoDomain}/oauth2/authorize?${params}`;
}

export async function beginLogin(config: RuntimeConfig): Promise<void> {
  window.location.assign(await createAuthorizationRequest(config));
}

export async function completeLogin(config: RuntimeConfig): Promise<Session> {
  const params = new URLSearchParams(window.location.search);
  const code = params.get("code");
  const state = params.get("state");
  const flow = JSON.parse(sessionStorage.getItem(FLOW_KEY) ?? "null") as
    | { verifier: string; state: string; nonce: string }
    | null;
  sessionStorage.removeItem(FLOW_KEY);
  if (!code || !flow || state !== flow.state) throw new Error("Invalid or expired sign-in callback");
  const response = await fetch(`https://${config.cognitoDomain}/oauth2/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "authorization_code",
      client_id: config.cognitoClientId,
      code,
      code_verifier: flow.verifier,
      redirect_uri: `${window.location.origin}/auth/callback`,
    }),
  });
  if (!response.ok) throw new Error("Cognito rejected the authorization code");
  const tokens = (await response.json()) as Record<string, string | number>;
  const claims = decodePayload(String(tokens.id_token));
  if (claims.nonce !== flow.nonce) throw new Error("Identity token nonce did not match");
  const session: Session = {
    idToken: String(tokens.id_token),
    accessToken: String(tokens.access_token),
    refreshToken: String(tokens.refresh_token),
    expiresAt: Date.now() + Number(tokens.expires_in) * 1000,
    email: typeof claims.email === "string" ? claims.email : undefined,
  };
  saveSession(session);
  history.replaceState({}, "", "/");
  return session;
}

export function readSession(): Session | null {
  try {
    const value = sessionStorage.getItem(SESSION_KEY);
    return value ? (JSON.parse(value) as Session) : null;
  } catch {
    return null;
  }
}

export function saveSession(session: Session): void {
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
}

export async function freshSession(config: RuntimeConfig): Promise<Session | null> {
  const current = readSession();
  if (!current) return null;
  if (current.expiresAt > Date.now() + 60_000) return current;
  const response = await fetch(`https://${config.cognitoDomain}/oauth2/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "refresh_token",
      client_id: config.cognitoClientId,
      refresh_token: current.refreshToken,
    }),
  });
  if (!response.ok) {
    sessionStorage.removeItem(SESSION_KEY);
    return null;
  }
  const tokens = (await response.json()) as Record<string, string | number>;
  const updated: Session = {
    ...current,
    idToken: String(tokens.id_token),
    accessToken: String(tokens.access_token),
    refreshToken: tokens.refresh_token ? String(tokens.refresh_token) : current.refreshToken,
    expiresAt: Date.now() + Number(tokens.expires_in) * 1000,
  };
  saveSession(updated);
  return updated;
}

export function logout(config: RuntimeConfig): void {
  sessionStorage.removeItem(SESSION_KEY);
  const params = new URLSearchParams({
    client_id: config.cognitoClientId,
    logout_uri: window.location.origin,
  });
  window.location.assign(`https://${config.cognitoDomain}/logout?${params}`);
}
