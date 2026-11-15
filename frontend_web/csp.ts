import type { Plugin } from "vite";

// Content-Security-Policy for the production build. It is delivered as a <meta> tag because the
// CloudFront flat-rate Free plan does not allow custom response headers policies (see
// infra/frontend.tf). `frame-ancestors` is ignored in a meta tag; the managed
// SecurityHeadersPolicy's X-Frame-Options header covers framing instead.
export const CONTENT_SECURITY_POLICY = [
  "default-src 'self'",
  "connect-src 'self' https://*.amazoncognito.com",
  "img-src 'self' data: blob: https://*.amazonaws.com",
  "font-src 'self'",
  "style-src 'self' 'unsafe-inline'",
  "script-src 'self'",
  "base-uri 'self'",
  "form-action 'self' https://*.amazoncognito.com",
].join("; ");

// Build-only: the Vite dev server injects inline scripts that `script-src 'self'` would block.
export function contentSecurityPolicyMeta(): Plugin {
  return {
    name: "csp-meta",
    apply: "build",
    transformIndexHtml() {
      return [
        {
          tag: "meta",
          attrs: { "http-equiv": "Content-Security-Policy", content: CONTENT_SECURITY_POLICY },
          injectTo: "head-prepend",
        },
      ];
    },
  };
}
