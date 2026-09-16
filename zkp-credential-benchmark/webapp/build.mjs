// Build script for the ZK Credential Demo web app.
//
// Why a build step exists at all, for a "plain HTML/CSS/JS" app:
// @noir-lang/noir_js and @aztec/bb.js are npm packages that use bare
// module specifiers (import ... from "@noir-lang/noir_js") and, for
// bb.js, Web Workers loaded via `new URL("./x.worker.js", import.meta.url)`.
// Neither of those resolve from a plain <script> tag without a bundler.
// esbuild is used here ONLY to resolve and bundle those imports into
// plain .js files -- there is no framework, no JSX, no dev server magic.
// The actual front-end (index.html, css, DOM code) is hand-written,
// ordinary HTML/CSS/JavaScript; you only ever re-run `npm run build`
// after editing something under src/.
import { build } from "esbuild";
import { fileURLToPath } from "url";
import path from "path";
import fs from "fs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const dist = path.join(__dirname, "dist");

fs.rmSync(dist, { recursive: true, force: true });
fs.mkdirSync(dist, { recursive: true });

// 1. Main application bundle (app code + noir_js + bb.js + ethers).
await build({
  entryPoints: [path.join(__dirname, "src/app.js")],
  bundle: true,
  format: "esm",
  target: "es2022",
  outfile: path.join(dist, "bundle.js"),
  minify: false,
  sourcemap: true,
});

// 2. bb.js's two Web Worker entry points, bundled separately so the
//    `new URL("./main.worker.js", import.meta.url)` / "./thread.worker.js"
//    calls inside the main bundle resolve to real files sitting right
//    next to bundle.js at runtime.
const bbjsBrowser = path.join(
  __dirname,
  "node_modules/@aztec/bb.js/dest/browser/barretenberg_wasm"
);

await build({
  entryPoints: [
    path.join(bbjsBrowser, "barretenberg_wasm_main/factory/browser/main.worker.js"),
  ],
  bundle: true,
  format: "esm",
  target: "es2022",
  outfile: path.join(dist, "main.worker.js"),
  sourcemap: true,
});

await build({
  entryPoints: [
    path.join(bbjsBrowser, "barretenberg_wasm_thread/factory/browser/thread.worker.js"),
  ],
  bundle: true,
  format: "esm",
  target: "es2022",
  outfile: path.join(dist, "thread.worker.js"),
  sourcemap: true,
});

// 3. Copy static assets (HTML/CSS and the compiled circuits) into dist/.
function copyDir(src, destDir) {
  fs.mkdirSync(destDir, { recursive: true });
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    const s = path.join(src, entry.name);
    const d = path.join(destDir, entry.name);
    if (entry.isDirectory()) copyDir(s, d);
    else fs.copyFileSync(s, d);
  }
}
copyDir(path.join(__dirname, "public"), dist);
copyDir(path.join(__dirname, "circuits"), path.join(dist, "circuits"));

// @noir-lang/noir_js pulls in two wasm-bindgen modules (noirc_abi, acvm_js)
// that fetch their .wasm binary via `new URL("x.wasm", import.meta.url)`
// instead of embedding it inline (unlike bb.js's own wasm, which IS
// embedded as a base64 data URI and needs no such copy). After esbuild
// bundles everything into one file, that resolves relative to bundle.js's
// own URL -- i.e. straight off the site root -- so these two files must
// sit right next to bundle.js with these exact names.
const wasmCopies = [
  ["node_modules/@noir-lang/noirc_abi/web/noirc_abi_wasm_bg.wasm", "noirc_abi_wasm_bg.wasm"],
  ["node_modules/@noir-lang/acvm_js/web/acvm_js_bg.wasm", "acvm_js_bg.wasm"],
];
for (const [src, destName] of wasmCopies) {
  fs.copyFileSync(path.join(__dirname, src), path.join(dist, destName));
}

console.log("Build complete -> webapp/dist/");
console.log("Run `npm run serve` (or any static file server) to try it.");
