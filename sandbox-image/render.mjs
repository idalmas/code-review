// Renders every harness state for the base and head copies of a component and records
// screenshots plus automatic checks. Runs inside the sandbox with no network.
//
// Usage: node render.mjs <job-dir> <spec.json>
//   spec: { versions: { base?: {appRoot, component, css?}, head?: {...} }, harness: "harness.tsx",
//           live?: "head" }   // also build that version as a static, clickable page
//   appRoot is "<version>/<path in repo>", e.g. "head/web".
import fs from "node:fs/promises";
import path from "node:path";
import react from "@vitejs/plugin-react";
import { chromium } from "playwright";
import { build, createServer } from "vite";
import tsconfigPaths from "vite-tsconfig-paths";

import { sourceTags } from "./source-tags.mjs";

const [jobDir, specFile] = process.argv.slice(2);
const spec = JSON.parse(await fs.readFile(path.join(jobDir, specFile), "utf8"));
const SHIMS = "/sandbox/shims";
const DEFAULT_VIEWPORT = { width: 1024, height: 768 };

const browser = await chromium.launch();
try {
  for (const [version, v] of Object.entries(spec.versions)) {
    const outDir = path.join(jobDir, "out", version);
    await fs.mkdir(outDir, { recursive: true });
    const report = await renderVersion(v, outDir).catch((err) => ({
      buildError: String(err?.stack ?? err).slice(0, 4000),
      states: [],
    }));
    if (spec.live === version && !report.buildError) {
      report.live = await buildLive(v, path.join(jobDir, "out", "live")).then(
        () => true,
        (err) => (console.error("live build failed:", err), false),
      );
    }
    await fs.writeFile(path.join(outDir, "report.json"), JSON.stringify(report, null, 2));
  }
} finally {
  await browser.close();
}

/** Writes the harness page into the app and returns the shared Vite config for it. */
async function prepare(v) {
  const appRoot = path.join(jobDir, v.appRoot);
  const harnessDir = path.join(appRoot, ".cr-harness");
  await fs.mkdir(harnessDir, { recursive: true });
  await fs.copyFile(path.join(jobDir, spec.harness), path.join(harnessDir, "harness.tsx"));
  await fs.copyFile("/sandbox/entry.tsx", path.join(harnessDir, "entry.tsx"));
  await fs.copyFile("/sandbox/inspector.ts", path.join(harnessDir, "inspector.ts"));
  const css = v.css ? `import ${JSON.stringify(path.join(appRoot, v.css))};\n` : "";
  await fs.writeFile(path.join(harnessDir, "main.tsx"), `${css}import "./entry";\n`);
  await fs.writeFile(
    path.join(harnessDir, "index.html"),
    `<!doctype html><html><head><meta charset="utf-8"></head>` +
      `<body style="margin:0"><div id="cr-root" style="display:inline-block;min-width:100%;padding:16px;box-sizing:border-box"></div>` +
      `<script type="module" src="./main.tsx"></script></body></html>`,
  );
  process.chdir(appRoot); // Tailwind and PostCSS resolve content and config from here.
  return {
    root: harnessDir,
    configFile: false,
    logLevel: "error",
    plugins: [
      sourceTags({ appRoot, repoPrefix: v.appRoot.split("/").slice(1).join("/") }),
      react(),
      tsconfigPaths({ root: appRoot }),
    ],
    resolve: {
      alias: [
        { find: "@target", replacement: path.join(appRoot, v.component) },
        { find: /^next\/link$/, replacement: `${SHIMS}/next-link.jsx` },
        { find: /^next\/image$/, replacement: `${SHIMS}/next-image.jsx` },
        { find: /^next\/navigation$/, replacement: `${SHIMS}/next-navigation.js` },
      ],
      dedupe: ["react", "react-dom"],
    },
  };
}

/** Static build of the harness (relative URLs) that Cypher serves for click-to-comment. */
async function buildLive(v, outDir) {
  const config = await prepare(v);
  await build({ ...config, base: "./", build: { outDir, emptyOutDir: true, sourcemap: false } });
}

async function renderVersion(v, outDir) {
  const config = await prepare(v);
  const appRoot = path.join(jobDir, v.appRoot);
  const server = await createServer({
    ...config,
    server: { host: "127.0.0.1", port: 0, fs: { allow: [appRoot, SHIMS, "/sandbox"] } },
  });
  await server.listen();
  const url = server.resolvedUrls.local[0];

  try {
    const page = await browser.newPage();
    const pageErrors = [];
    page.on("pageerror", (e) => pageErrors.push(String(e?.stack ?? e)));
    await page.goto(url, { waitUntil: "load", timeout: 60_000 });
    await page.waitForFunction(() => window.__CR?.done, null, { timeout: 60_000 }).catch(() => {});
    const list = await page.evaluate(() => window.__CR?.states);
    await page.close();
    if (!list) throw new Error(`Harness failed to load:\n${pageErrors.join("\n")}`);

    const states = [];
    for (let i = 0; i < list.length; i++) states.push(await renderState(url, i, list[i], outDir));
    return { states };
  } finally {
    await server.close();
  }
}

async function renderState(url, i, state, outDir) {
  const viewport = state.viewport ?? DEFAULT_VIEWPORT;
  const page = await browser.newPage({ viewport });
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e?.message ?? e)));
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  const started = Date.now();
  await page.goto(`${url}?state=${i}`, { waitUntil: "load", timeout: 30_000 });
  const settled = await page
    .waitForFunction(() => window.__CR?.done, null, { timeout: 10_000 })
    .then(() => true, () => false);
  await page.waitForTimeout(150); // let fonts/layout settle
  const checks = await page.evaluate(() => {
    const overflowing = [...document.querySelectorAll("#cr-root *")].filter((el) => {
      const s = getComputedStyle(el);
      // >4px so decorations (badges hanging off an avatar) don't count as broken layout.
      return s.display !== "inline" && s.overflowX === "visible" && el.scrollWidth > el.clientWidth + 4;
    });
    return {
      boundaryErrors: window.__CR?.errors ?? [],
      pageOverflow: document.documentElement.scrollWidth > window.innerWidth,
      overflowingElements: overflowing.length,
    };
  });
  const file = `state-${i}.png`;
  // Crop to what the component actually drew (plus padding), not the whole viewport.
  const clip = await page.evaluate(() => {
    const boxes = [...document.querySelectorAll("#cr-root *")].map((el) => el.getBoundingClientRect());
    const drawn = boxes.filter((b) => b.width > 0 && b.height > 0);
    if (!drawn.length) return null;
    const x = Math.max(0, Math.min(...drawn.map((b) => b.left)) - 16);
    const y = Math.max(0, Math.min(...drawn.map((b) => b.top)) - 16);
    const right = Math.max(...drawn.map((b) => b.right)) + 16;
    const bottom = Math.max(...drawn.map((b) => b.bottom)) + 16;
    return { x, y, width: Math.min(right - x, 4000), height: Math.min(bottom - y, 4000) };
  });
  await page.screenshot({ path: path.join(outDir, file), clip: clip ?? undefined, fullPage: !clip });
  await page.close();
  return {
    name: state.name,
    viewport,
    image: file,
    ms: Date.now() - started,
    timedOut: !settled,
    errors: [...checks.boundaryErrors, ...errors].map((e) => e.slice(0, 2000)),
    pageOverflow: checks.pageOverflow,
    overflowingElements: checks.overflowingElements,
  };
}
