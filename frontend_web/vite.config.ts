import { defineConfig, type Plugin } from "vitest/config";
import react from "@vitejs/plugin-react";

// Forward-slash filesystem path for a file URL (also strips the leading slash before a Windows drive letter).
const toPath = (url: URL) => decodeURIComponent(url.pathname).replace(/^\/([A-Za-z]:)/, "$1");
const packageRoot = toPath(new URL(".", import.meta.url));
const testsRoot = toPath(new URL("../tests/frontend_web/", import.meta.url));

// Tests live in the repo-level tests/ folder, outside this package, so Node resolution from there never
// reaches frontend_web/node_modules. Resolve their bare imports (vitest, @testing-library/*, ...) as if
// they were imported from this package.
function resolveTestDependencies(): Plugin {
  return {
    name: "resolve-test-dependencies",
    enforce: "pre",
    async resolveId(source, importer, options) {
      const bare = !source.startsWith(".") && !source.startsWith("/") && !/^[A-Za-z]:/.test(source);
      if (!bare || !importer || !importer.replaceAll("\\", "/").startsWith(testsRoot)) return null;
      return this.resolve(source, `${packageRoot}package.json`, { ...options, skipSelf: true });
    },
  };
}

export default defineConfig({
  plugins: [react(), resolveTestDependencies()],
  server: {
    fs: { allow: [".."] },
    proxy: {
      "/api": "http://localhost:8080",
    },
  },
  test: {
    environment: "jsdom",
    include: ["../tests/frontend_web/**/*.test.{ts,tsx}"],
    setupFiles: "../tests/frontend_web/setup.ts",
  },
});
