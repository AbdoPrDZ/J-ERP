import { model } from './model';
import type { DraftChange } from './model';

export const DRAFT_CHANGE_DELAY = 800;
const STORAGE_PREFIX = 'jerp.draft';

function storageKey(
  modelName: string,
  recordId?: number | string | null,
  scope?: string,
): string {
  const identity = recordId === null || recordId === undefined ? 'new' : String(recordId);
  return `${STORAGE_PREFIX}.${scope ?? ''}.${modelName}.${identity}`;
}

function randomToken(): string {
  const randomUUID = globalThis.crypto?.randomUUID;
  if (randomUUID) {
    return randomUUID.call(globalThis.crypto);
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

/** Return the session token for a form, creating it on first use. */
export function draftToken(
  modelName: string,
  recordId?: number | string | null,
  scope?: string,
): string {
  const key = storageKey(modelName, recordId, scope);
  try {
    const existing = window.sessionStorage.getItem(key);
    if (existing) {
      return existing;
    }
    const token = randomToken();
    window.sessionStorage.setItem(key, token);
    return token;
  } catch {
    return randomToken();
  }
}

export function clearDraftToken(
  modelName: string,
  recordId?: number | string | null,
  scope?: string,
): void {
  try {
    window.sessionStorage.removeItem(storageKey(modelName, recordId, scope));
  } catch {
    // ignore
  }
}

/**
 * Batches field changes for one draft and sends them after a short idle
 * period. Only one request is in flight per draft.
 */
export class DraftQueue {
  private pending: Record<string, unknown> = {};
  private timer: ReturnType<typeof setTimeout> | null = null;
  private inFlight: Promise<void> | null = null;
  private disposed = false;
  private errors: Record<string, string> = {};
  private warnings: unknown[] = [];

  constructor(
    private readonly modelName: string,
    private readonly draftId: number,
    private readonly onResult: (change: DraftChange) => void,
    private readonly onError: (error: Error) => void,
  ) {}

  get lastErrors(): Record<string, string> {
    return this.errors;
  }

  get lastWarnings(): unknown[] {
    return this.warnings;
  }

  pendingValues(): Record<string, unknown> {
    return { ...this.pending };
  }

  pendingNames(): Set<string> {
    return new Set(Object.keys(this.pending));
  }

  setField(name: string, value: unknown): void {
    if (this.disposed) {
      return;
    }
    this.pending[name] = value;
    this.schedule();
  }

  private schedule(): void {
    if (this.timer) {
      clearTimeout(this.timer);
    }
    this.timer = setTimeout(() => {
      this.timer = null;
      void this.flush().catch(() => {
        // The error is reported through onError; do not spam retries.
      });
    }, DRAFT_CHANGE_DELAY);
  }

  async flush(): Promise<void> {
    if (this.disposed) {
      return;
    }
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }
    if (this.inFlight) {
      await this.inFlight;
    }
    if (this.disposed || Object.keys(this.pending).length === 0) {
      return;
    }

    const batch = this.pending;
    this.pending = {};
    const request = (async () => {
      try {
        const result = await model(this.modelName).changeDraft(
          this.draftId,
          batch,
        );
        this.errors = result.errors ?? {};
        this.warnings = result.warnings ?? [];
        this.onResult(result);
      } catch (error) {
        this.pending = { ...batch, ...this.pending };
        this.onError(error as Error);
        throw error;
      }
    })();

    this.inFlight = request;
    try {
      await request;
    } finally {
      this.inFlight = null;
    }

    if (Object.keys(this.pending).length > 0 && !this.disposed) {
      await this.flush();
    }
  }

  dispose(): void {
    this.disposed = true;
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }
  }
}
