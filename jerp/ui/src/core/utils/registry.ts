export type UtilFn = (...args: any[]) => unknown;

/**
 * Registry for J-ERP client utilities, kept separate from the field and view
 * registries. Modules can register/override utilities by name.
 */
class UtilsRegistry {
  private utils = new Map<string, UtilFn>();

  register(name: string, fn: UtilFn): void {
    this.utils.set(name, fn);
  }

  get(name: string): UtilFn | undefined {
    return this.utils.get(name);
  }

  call<T = unknown>(name: string, ...args: unknown[]): T {
    const fn = this.utils.get(name);
    if (!fn) {
      throw new Error(`Unknown util "${name}".`);
    }
    return fn(...args) as T;
  }

  keys(): string[] {
    return [...this.utils.keys()];
  }
}

export const utilsRegistry = new UtilsRegistry();
