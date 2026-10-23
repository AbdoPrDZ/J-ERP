import { viewsRegistry } from '../../registry';
import { viewRegistry } from './registry';
import { FormView } from './FormView';
import { TableView } from './Table';
import { CardsView } from './Cards';
import { StandardView } from './StandardView';

/** Register the standard views and the ``jerp.view`` host component. */
export function registerBuiltinViews(): void {
  viewRegistry.register('form', FormView);
  viewRegistry.register('table', TableView);
  viewRegistry.register('cards', CardsView);

  // Any page whose context carries a view descriptor mounts this host.
  viewsRegistry.register('jerp.view', () =>
    Promise.resolve({ default: StandardView }),
  );
}

export { viewRegistry } from './registry';
export { StandardView } from './StandardView';
export { TableView } from './Table';
export { CardsView } from './Cards';
export { FormView } from './FormView';
