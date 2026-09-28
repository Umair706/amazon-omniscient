// LLM-generated fields are meant to be plain text, but smaller or local models
// (e.g. a local Ollama model) sometimes return an object or array where a string
// was expected. Rendering one of those directly crashes React with
// "Objects are not valid as a React child". This coerces any LLM value into a
// safe display string, so the UI degrades gracefully instead of crashing when
// the model returns an unexpected shape.

function humanizeKey(key: string): string {
  return key.replace(/_/g, " ");
}

// Returns a string safe to render as a React child, whatever shape the value is.
export function toDisplayText(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) {
    return value.map(toDisplayText).filter(Boolean).join("\n");
  }
  if (typeof value === "object") {
    // An unexpected object becomes readable "key: value" lines rather than a crash.
    return Object.entries(value as Record<string, unknown>)
      .map(([key, val]) => `${humanizeKey(key)}: ${toDisplayText(val)}`)
      .join("\n");
  }
  return String(value);
}
