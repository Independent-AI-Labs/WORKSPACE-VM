import test from "node:test";
import assert from "node:assert/strict";
import { createToastQueue, MAX_PENDING_TOASTS, type ToastBody } from "../src/toast-queue.ts";

function body(message: string, duration = 10): ToastBody {
  return { title: "Moderator", message, variant: "info", duration };
}

function tick(): Promise<void> {
  return new Promise((resolve) => setImmediate(resolve));
}

function transitions(shown: string[]): string[] {
  return shown.filter((message, index) => index === 0 || message !== shown[index - 1]);
}

test("queue shows one toast at a time and waits for each duration", async () => {
  const shown: string[] = [];
  const waits: number[] = [];
  let release: (() => void) | undefined;
  const queue = createToastQueue({
    show: async (entry) => {
      shown.push(entry.message);
    },
    onError: () => {
      throw new Error("unexpected toast error");
    },
    wait: (ms) => {
      waits.push(ms);
      return new Promise<void>((resolve) => {
        release = resolve;
      });
    },
  });

  queue.push("s1", body("one", 10));
  queue.push("s1", body("two", 20));
  await tick();
  assert.deepEqual(shown, ["one"]);

  release?.();
  await tick();
  assert.deepEqual(shown, ["one", "two"]);

  release?.();
  await queue.flush();
  assert.deepEqual(waits, [10, 20]);
});

test("a failed toast is reported and the next toast still shows", async () => {
  const shown: string[] = [];
  const errors: string[] = [];
  const queue = createToastQueue({
    show: async (entry) => {
      if (entry.message === "bad") throw new Error("toast failed");
      shown.push(entry.message);
    },
    onError: (sessionID, error) => {
      errors.push(`${sessionID}:${error instanceof Error ? error.message : String(error)}`);
    },
    wait: async () => {},
  });

  queue.push("s1", body("bad"));
  queue.push("s1", body("good"));
  await queue.flush();

  assert.deepEqual(errors, ["s1:toast failed"]);
  assert.deepEqual(transitions(shown), ["good"]);
});

test("deleting a session removes its pending toasts", async () => {
  const shown: string[] = [];
  const queue = createToastQueue({
    show: async (entry) => {
      shown.push(entry.message);
    },
    onError: () => {
      throw new Error("unexpected toast error");
    },
    wait: async () => {},
  });

  queue.push("s1", body("current"));
  queue.push("s1", body("pending"));
  queue.push("s2", body("other"));
  queue.removeSession("s1");
  await queue.flush();

  assert.deepEqual(transitions(shown), ["current", "other"]);
});

test("queue drops the oldest pending toast when full", async () => {
  const shown: string[] = [];
  const queue = createToastQueue({
    show: async (entry) => {
      shown.push(entry.message);
    },
    onError: () => {
      throw new Error("unexpected toast error");
    },
    wait: async () => {},
  });

  const total = MAX_PENDING_TOASTS + 4;
  for (let index = 1; index <= total; index += 1) {
    queue.push("s1", body(String(index)));
  }
  await queue.flush();

  const order = transitions(shown);
  assert.equal(order[0], "1");
  assert.equal(order[1], String(total - MAX_PENDING_TOASTS + 1));
  assert.equal(order.length, MAX_PENDING_TOASTS + 1);
});
