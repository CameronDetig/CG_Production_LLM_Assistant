import { describe, expect, it } from "vitest";
import { CONTENT_SECURITY_POLICY } from "../../frontend_web/csp";

const directives = new Map(
  CONTENT_SECURITY_POLICY.split(";").map((directive) => {
    const [name, ...sources] = directive.trim().split(/\s+/);
    return [name, sources] as const;
  }),
);

describe("Content-Security-Policy meta tag", () => {
  it("only runs scripts from the site itself", () => {
    expect(directives.get("script-src")).toEqual(["'self'"]);
    expect(directives.get("default-src")).toEqual(["'self'"]);
  });

  it("allows the API and Cognito sign-in", () => {
    expect(directives.get("connect-src")).toEqual(["'self'", "https://*.amazoncognito.com"]);
    expect(directives.get("form-action")).toContain("https://*.amazoncognito.com");
  });

  it("allows presigned S3 thumbnails", () => {
    expect(directives.get("img-src")).toContain("https://*.amazonaws.com");
  });

  it("omits frame-ancestors, which browsers ignore in a meta tag", () => {
    expect(directives.has("frame-ancestors")).toBe(false);
  });
});
