# CG Production Assistant Web

React/Vite single-page application for the production assistant. Production
configuration is loaded at runtime from `/config.json`, which Terraform owns.

## Local development

1. Copy `public/config.json` values from Terraform outputs or an approved test
   Cognito public client.
2. Run the backend ASGI app on port 8080.
3. Install dependencies and start Vite:

   ```powershell
   npm install
   npm run dev
   ```

Vite proxies `/api` to `http://localhost:8080`. The callback URL for local
managed login must also be registered in Cognito before testing authentication.

## Content-Security-Policy

The CSP is a `<meta>` tag that `csp.ts` injects into `index.html` during
`npm run build`. It is not an HTTP header, because the CloudFront flat-rate Free
plan does not allow custom response headers policies. The dev server does not
add it, since Vite's dev mode needs inline scripts. Edit the policy in `csp.ts`,
and add any new image, API or sign-in origin there. `frame-ancestors` does not
work in a meta tag; CloudFront's managed `X-Frame-Options` header blocks framing
instead.
