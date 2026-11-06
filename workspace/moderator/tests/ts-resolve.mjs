export async function resolve(specifier, context, nextResolve) {
  if (specifier.startsWith("./") || specifier.startsWith("../")) {
    const name = specifier.split("/").pop() ?? specifier;
    const candidates = !name.includes(".")
      ? [`${specifier}.ts`, `${specifier}/index.ts`]
      : specifier.endsWith(".js")
        ? [`${specifier.slice(0, -3)}.ts`, `${specifier.slice(0, -3)}/index.ts`]
        : [];
    for (const candidate of candidates) {
      try {
        return await nextResolve(candidate, context);
      } catch {
        continue;
      }
    }
  }
  return nextResolve(specifier, context);
}
