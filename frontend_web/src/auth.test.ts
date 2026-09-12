import { beforeEach, describe, expect, it } from "vitest";
import { createAuthorizationRequest, readSession, saveSession } from "./auth";
import type { RuntimeConfig, Session } from "./types";

const config: RuntimeConfig = {
  cognitoDomain: "example.auth.us-east-1.amazoncognito.com",
  cognitoClientId: "public-client",
  oauthScopes: ["openid", "email"],
};

describe("Cognito session and PKCE", () => {
  beforeEach(() => sessionStorage.clear());

  it("creates a code-flow authorization request with PKCE, state, and nonce", async () => {
    const url = new URL(await createAuthorizationRequest(config));
    expect(url.pathname).toBe("/oauth2/authorize");
    expect(url.searchParams.get("response_type")).toBe("code");
    expect(url.searchParams.get("code_challenge_method")).toBe("S256");
    expect(url.searchParams.get("code_challenge")).toBeTruthy();
    expect(url.searchParams.get("state")).toBeTruthy();
    expect(url.searchParams.get("nonce")).toBeTruthy();
    expect(url.searchParams.has("client_secret")).toBe(false);
  });

  it("stores the session only in sessionStorage", () => {
    const session: Session = {
      idToken: "id",
      accessToken: "access",
      refreshToken: "refresh",
      expiresAt: 123,
      email: "artist@example.com",
    };
    saveSession(session);
    expect(readSession()).toEqual(session);
    expect(localStorage.length).toBe(0);
  });
});
