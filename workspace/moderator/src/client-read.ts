export function requireData<T>(payload: { data?: T; error?: unknown }, label: string): T {
  if (payload.data === undefined) {
    const detail = payload.error === undefined ? "missing data" : JSON.stringify(payload.error);
    throw new Error(`${label}: ${detail}`);
  }
  return payload.data;
}
