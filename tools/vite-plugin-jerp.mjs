/**
 * Vite dev plugin for J-ERP.
 *
 * In dev the app is served by Vite (HMR) instead of the built `data/ui`.
 * This plugin injects the same payload the Python renderer injects in
 * production:
 *
 *  - __JERP_VIEWS__   : page name -> source module url (modules/<m>/ui/src/views)
 *  - __JERP_ROUTES__  : endpoint -> view
 *  - __JERP_PAGES__   : view -> { auth, header, menu }
 *  - __JERP_MENUS__   : nested menu tree (groups have `children`)
 *  - __JERP_CONTEXT__ : empty (dev)
 *
 * React stays a single instance because Vite serves both the shell and the
 * module views, so no import map is needed in dev.
 */

import fs from 'node:fs';
import path from 'node:path';

function toSnake(name) {
  return name
    .replace(/([a-z0-9])([A-Z])/g, '$1_$2')
    .replace(/([A-Z]+)([A-Z][a-z])/g, '$1_$2')
    .toLowerCase();
}

function viewFiles(dir) {
  if (!fs.existsSync(dir)) {
    return [];
  }
  const found = [];
  const walk = (current) => {
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const full = path.join(current, entry.name);
      if (entry.isDirectory()) {
        walk(full);
      } else if (/\.(tsx|ts)$/.test(entry.name)) {
        found.push(full);
      }
    }
  };
  walk(dir);
  return found;
}

function menuHref(item) {
  const endpoint = item.endpoint || item.path;
  const params = item.params || {};
  if (endpoint) {
    const query = new URLSearchParams(params).toString();
    return query ? `${endpoint}?${query}` : endpoint;
  }
  return '/view?' + new URLSearchParams({ name: item.view, ...params }).toString();
}

function menuNode(item) {
  if (!item || item.hide || !item.label) {
    return null;
  }
  const node = { label: item.label, sequence: item.sequence ?? 0 };
  if (item.view) {
    node.href = menuHref(item);
    node.auth = item.auth !== false;
  }
  if (item.img) {
    node.img = item.img;
  }
  if (item.description) {
    node.description = item.description;
  }
  if (item.add_to_home) {
    node.add_to_home = true;
  }
  const children = (item.children || []).map(menuNode).filter(Boolean);
  if (children.length) {
    children.sort((a, b) => (a.sequence ?? 0) - (b.sequence ?? 0) || a.label.localeCompare(b.label));
    node.children = children;
  }
  return node;
}

function firstHref(item) {
  if (!item || typeof item !== 'object') {
    return null;
  }
  if (item.view) {
    return menuHref(item);
  }
  for (const child of item.children || []) {
    const href = firstHref(child);
    if (href) {
      return href;
    }
  }
  return null;
}

function collectHome(moduleName, items, rootSequence, out) {
  for (const item of items || []) {
    if (!item || typeof item !== 'object') {
      continue;
    }
    if (item.add_to_home) {
      const href = firstHref(item);
      if (href) {
        out.push({
          label: item.label || item.view || 'Page',
          href,
          description: item.description,
          img: item.img,
          module: moduleName,
          sequence: rootSequence,
        });
      }
    }
    if (item.children) {
      collectHome(moduleName, item.children, rootSequence, out);
    }
  }
}

export default function jerpDev(modulesDir = 'modules') {
  const modulesRoot = path.resolve(modulesDir);
  let backend = 'http://127.0.0.1:1347';
  let installedModules = new Set(['core']);

  return {
    name: 'jerp-dev',
    apply: 'serve',

    async config() {
      // Collect the backend's URL prefixes instead of hardcoding proxies.
      let port = 1347;
      try {
        const config = JSON.parse(fs.readFileSync(path.resolve('jerp.config.json'), 'utf8'));
        port = config?.app?.port ?? port;
      } catch {
        // keep default
      }
      backend = `http://127.0.0.1:${port}`;

      const proxy = {};
      try {
        const response = await fetch(`${backend}/__endpoints`);
        if (response.ok) {
          const { endpoints } = await response.json();
          for (const prefix of endpoints ?? []) {
            proxy[prefix] = { target: backend, changeOrigin: true };
          }
        }
      } catch {
        // Backend not running yet - start it before `npm run dev`.
      }

      return { server: { proxy } };
    },

    configureServer(server) {
      server.middlewares.use(async (req, _res, next) => {
        const acceptsHtml = (req.headers.accept || '').includes('text/html');
        if (!acceptsHtml) {
          return next();
        }
        try {
          const response = await fetch(`${backend}/__modules`, {
            headers: { cookie: req.headers.cookie || '' },
          });
          if (response.ok) {
            const data = await response.json();
            installedModules = new Set(
              Array.isArray(data.modules) ? data.modules : [],
            );
          } else {
            installedModules = new Set(['core']);
          }
        } catch {
          // Without the backend we cannot know what is installed. Keep the
          // shell minimal instead of leaking every module on disk.
          installedModules = new Set(['core']);
        }
        next();
      });
    },

    transformIndexHtml(html) {
      const views = {};
      const routes = {};
      const pages = {};
      const menus = [];
      const home = [];
      const configs = [];
      const enabled = installedModules;

      if (fs.existsSync(modulesRoot)) {
        for (const entry of fs.readdirSync(modulesRoot, { withFileTypes: true })) {
          if (!entry.isDirectory()) {
            continue;
          }
          const moduleDir = path.join(modulesRoot, entry.name);
          const configPath = path.join(moduleDir, 'configure.json');
          if (!fs.existsSync(configPath)) {
            continue;
          }

          let config = {};
          try {
            config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
          } catch {
            config = {};
          }
          const name = config.name || entry.name;

          // Hide modules that are not installed in the selected database.
          // With no database selected only the core shell is needed.
          if (enabled) {
            const include =
              enabled.size === 0 ? name === 'core' : enabled.has(name);
            if (!include) {
              continue;
            }
          }

          configs.push(config);

          const viewsDir = path.join(moduleDir, 'ui', 'src', 'views');
          for (const file of viewFiles(viewsDir)) {
            const rel = path.relative(viewsDir, file).split(path.sep).join('/');
            const base = rel.replace(/\.(tsx|ts)$/, '');
            const key = `${name}.${toSnake(path.basename(base))}`;
            views[key] = `/${modulesDir}/${name}/ui/src/views/${base}.tsx`;
          }

          const walk = (entries) => {
            for (const item of entries || []) {
              if (!item || typeof item !== 'object') {
                continue;
              }
              if (item.view) {
                pages[item.view] = {
                  auth: item.auth !== false,
                  header: item.header !== false,
                  menu: item.menu !== false,
                  drawer: item.drawer !== false,
                };
                const endpoint = item.endpoint || item.path;
                if (endpoint) {
                  routes[endpoint] = item.view;
                }
              }
              if (item.children) {
                walk(item.children);
              }
            }
          };
          walk(config.routes || config.pages || []);

          for (const item of config.routes || config.pages || []) {
            if (item && typeof item === 'object') {
              collectHome(name, [item], item.sequence ?? 0, home);
            }
          }
        }
      }

      for (const config of configs) {
        for (const item of config.routes || config.pages || []) {
          const node = menuNode(item);
          if (node) {
            menus.push(node);
          }
        }
      }
      menus.sort((a, b) => (a.sequence ?? 0) - (b.sequence ?? 0) || a.label.localeCompare(b.label));

      home.sort((a, b) => (a.sequence ?? 0) - (b.sequence ?? 0));
      const seen = new Set();
      const homeEntries = home.filter((entry) => {
        if (seen.has(entry.href)) {
          return false;
        }
        seen.add(entry.href);
        return true;
      });

      const inject = [
        `<script id="__JERP_VIEWS__" type="application/json">${JSON.stringify(views)}</script>`,
        `<script id="__JERP_ROUTES__" type="application/json">${JSON.stringify(routes)}</script>`,
        `<script id="__JERP_PAGES__" type="application/json">${JSON.stringify(pages)}</script>`,
        `<script id="__JERP_MENUS__" type="application/json">${JSON.stringify(menus)}</script>`,
        `<script id="__JERP_HOME__" type="application/json">${JSON.stringify(homeEntries)}</script>`,
        `<script id="__JERP_CONTEXT__" type="application/json">{}</script>`,
      ].join('\n    ');

      if (html.includes('<!--jerp:body-->')) {
        return html.replace('<!--jerp:body-->', inject);
      }
      return html.replace('</body>', `    ${inject}\n  </body>`);
    },
  };
}
