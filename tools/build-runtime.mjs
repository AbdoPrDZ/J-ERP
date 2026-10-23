/**
 * Build the shared React runtime.
 *
 * Module view bundles and the shell both mark `react`, `react/jsx-runtime` and
 * `react-dom/client` as external; an import map points those specifiers at the
 * file produced here, guaranteeing a single React instance everywhere.
 *
 * React ships as CommonJS (no ESM entry), so `export *` cannot enumerate its
 * names. Instead we generate explicit re-exports from React's actual runtime
 * keys, which keeps this correct across React versions.
 */

import { build } from 'esbuild';
import { createRequire } from 'node:module';
import path from 'node:path';

const require = createRequire(import.meta.url);

const RESERVED = new Set(['default']);

function exportableNames(module) {
  return Object.keys(module).filter(
    (name) => /^[$A-Za-z_][$\w]*$/.test(name) && !RESERVED.has(name) && !name.startsWith('__'),
  );
}

function reexport(namespace, module, seen) {
  const lines = [`import * as ${namespace} from ${JSON.stringify(module)};`];
  for (const name of exportableNames(require(module))) {
    if (seen.has(name)) {
      continue;
    }
    seen.add(name);
    lines.push(`export const ${name} = ${namespace}.${name};`);
  }
  return lines;
}

const seen = new Set();
const contents = [
  ...reexport('__react', 'react', seen),
  ...reexport('__jsx', 'react/jsx-runtime', seen),
  ...reexport('__dom', 'react-dom/client', seen),
].join('\n');

const outfile = path.resolve('data/ui/react-runtime.js');

await build({
  stdin: {
    contents,
    resolveDir: process.cwd(),
    sourcefile: 'jerp-react-runtime.js',
    loader: 'js',
  },
  bundle: true,
  format: 'esm',
  outfile,
  sourcemap: true,
  logLevel: 'warning',
});

console.log(`built ${path.relative(process.cwd(), outfile)}`);
