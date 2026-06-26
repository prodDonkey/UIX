export function serializeDate(value: Date): string {
  return value.toISOString().replace(/\.\d{3}Z$/, "");
}
