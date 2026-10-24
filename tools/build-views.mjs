/**
 * Build module view bundles.
 *
 * Each module's `ui/src/views/*.tsx` is compiled to ESM in `cache/view/<m>/`,
 * with React and the J-ERP UI kit left external (resolved at runtime by the
 * import map). `cache/view/<m>/manifest.json` maps view keys to their files.
 *
 * Output goes to the cache (not the source tree) and is only rebuilt when a
 * module is installed/updated.
 *
 * Usage:
 *   node tools/build-views.mjs            # all modules
 *   node tools/build-views.mjs core stock # selected modules
 */

import { build } from 'esbuild';
import fs from 'node:fs';
import path from 'node:path';

const EXTERNAL = [
  'react',
  'react-dom',
  'react-dom/client',
  'react/jsx-runtime',
  '@jerp/ui',
];

const modulesDir = path.resolve('modules');

function toSnake(name) {
  return name
    .replace(/([a-z0-9])([A-Z])/g, '$1_$2')
    .replace(/([A-Z]+)([A-Z][a-z])/g, '$1_$2')
    .toLowerCase();
}

/** The model a view's `<Page model="...">` renders, if it declares one. */
function pageModel(file) {
  try {
    const source = fs.readFileSync(file, 'utf8');
    const tag = source.match(/<Page\b[\s\S]*?>/);
    if (!tag) {
      return null;
    }
    const match = tag[0].match(/\bmodel=["']([^"']+)["']/);
    return match ? match[1] : null;
  } catch {
    return null;
  }
}

function listModuleDirs(filter) {
  if (!fs.existsSync(modulesDir)) {
    return [];
  }
  return fs
    .readdirSync(modulesDir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .filter((name) => !filter.length || filter.includes(name))
    .filter((name) => fs.existsSync(path.join(modulesDir, name, 'configure.json')));
}

function viewFiles(viewsDir) {
  if (!fs.existsSync(viewsDir)) {
    return [];
  }
  const found = [];
  const walk = (dir) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(full);
      } else if (entry.name.endsWith('.tsx') || entry.name.endsWith('.ts')) {
        found.push(full);
      }
    }
  };
  walk(viewsDir);
  return found;
}

function declaredViews(configurePath) {
  if (!fs.existsSync(configurePath)) {
    return [];
  }
  let config;
  try {
    config = JSON.parse(fs.readFileSync(configurePath, 'utf8'));
  } catch {
    return [];
  }
  const result = [];
  const walk = (entries) => {
    for (const item of entries || []) {
      if (item && item.view) {
        result.push(item.view);
      }
      if (item && item.children) {
        walk(item.children);
      }
    }
  };
  walk(config.routes || config.pages || []);
  return result;
}

const filter = process.argv.slice(2);
let built = 0;
const missing = [];

for (const moduleName of listModuleDirs(filter)) {
  const moduleRoot = path.join(modulesDir, moduleName);
  const viewsDir = path.join(moduleRoot, 'ui', 'src', 'views');
  const outDir = path.resolve('data', 'view', moduleName);
  const entryPoints = viewFiles(viewsDir);
  const manifest = { module: moduleName, views: {}, page_models: {} };

  for (const entry of entryPoints) {
    const rel = path.relative(viewsDir, entry);
    const base = rel.replace(/\.(tsx|ts)$/, '');
    const key = `${moduleName}.${toSnake(path.basename(base))}`;
    const out = `${base.split(path.sep).join('/')}.js`;
    manifest.views[key] = out;
    const model = pageModel(entry);
    if (model) {
      manifest.page_models[key] = model;
    }
  }

  if (entryPoints.length) {
    fs.mkdirSync(outDir, { recursive: true });

    await build({
      entryPoints,
      outdir: outDir,
      outbase: viewsDir,
      bundle: true,
      format: 'esm',
      target: 'es2022',
      jsx: 'automatic',
      sourcemap: true,
      external: EXTERNAL,
      logLevel: 'warning',
    });

    fs.writeFileSync(
      path.join(outDir, 'manifest.json'),
      `${JSON.stringify(manifest, null, 2)}\n`,
    );

    built += 1;
    console.log(
      `built ${moduleName} -> data/view/${moduleName}: ${Object.keys(manifest.views).join(', ')}`,
    );
  }

  for (const view of declaredViews(path.join(moduleRoot, 'configure.json'))) {
    if (!manifest.views[view]) {
      missing.push(`${moduleName}: ${view}`);
    }
  }
}

if (missing.length) {
  console.error('Missing view files for declared menu entries:');
  for (const item of missing) {
    console.error(`  - ${item}`);
  }
  process.exitCode = 1;
}

if (!built) {
  console.log('no module views to build');
}
