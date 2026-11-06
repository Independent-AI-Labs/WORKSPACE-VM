export type ToastBody = {
  title: string;
  message: string;
  variant: string;
  duration: number;
};

export interface ToastQueue {
  push(sessionID: string, body: ToastBody): void;
  removeSession(sessionID: string): void;
  flush(): Promise<void>;
}

export const MAX_PENDING_TOASTS = 16;

export function createToastQueue(input: {
  show: (body: ToastBody) => Promise<unknown>;
  onError: (sessionID: string, error: unknown) => void;
  wait?: (ms: number) => Promise<void>;
}): ToastQueue {
  const pending: Array<{ sessionID: string; body: ToastBody }> = [];
  const pause = input.wait ?? delay;
  let active: Promise<void> | null = null;

  const run = async (): Promise<void> => {
    while (pending.length > 0) {
      const entry = pending.shift();
      if (entry === undefined) break;
      try {
        await input.show(entry.body);
        await pause(entry.body.duration);
      } catch (error) {
        input.onError(entry.sessionID, error);
      }
    }
  };

  const start = (): void => {
    if (active !== null) return;
    active = run().finally(() => {
      active = null;
      if (pending.length > 0) start();
    });
  };

  return {
    push(sessionID: string, body: ToastBody): void {
      pending.push({ sessionID, body });
      if (pending.length > MAX_PENDING_TOASTS) pending.shift();
      start();
    },
    removeSession(sessionID: string): void {
      for (let index = pending.length - 1; index >= 0; index -= 1) {
        if (pending[index].sessionID === sessionID) pending.splice(index, 1);
      }
    },
    async flush(): Promise<void> {
      while (active !== null) await active;
    },
  };
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => {
    const timer = setTimeout(resolve, ms);
    timer.unref();
  });
}
