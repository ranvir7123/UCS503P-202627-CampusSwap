// Build every page's CSS and copy fonts into public/fonts.
// Run with: npm run build   (from code/frontend)
import { execFileSync } from "node:child_process";
import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const modules = join(root, "node_modules");
const fontsOut = join(root, "public", "fonts");
mkdirSync(fontsOut, { recursive: true });

const fonts = [
  ...[400, 500, 600, 700, 800].map((w) => `@fontsource/plus-jakarta-sans/files/plus-jakarta-sans-latin-${w}-normal.woff2`),
  ...[400, 500, 600, 700].map((w) => `@fontsource/jetbrains-mono/files/jetbrains-mono-latin-${w}-normal.woff2`),
  "material-symbols/material-symbols-outlined.woff2",
];
for (const font of fonts) {
  copyFileSync(join(modules, font), join(fontsOut, font.split("/").pop()));
}
console.log(`Copied ${fonts.length} font files`);

const cli = join(modules, "tailwindcss", "lib", "cli.js");
for (const page of ["login", "dashboard", "rooms", "admin", "slots"]) {
  execFileSync(process.execPath, [
    cli, "-c", `tailwind/${page}.config.cjs`, "-i", "src/tailwind.css", "-o", `public/assets/${page}.css`, "--minify",
  ], { cwd: root, stdio: "inherit" });
}
