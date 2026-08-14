import type { ConsultaResponse } from "./types";

const BASE =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ??
  "http://localhost:8000";

export async function consultar(
  pregunta: string,
  threadId?: string,
  signal?: AbortSignal,
): Promise<ConsultaResponse> {
  let res: Response;
  try {
    res = await fetch(`${BASE}/v1/consultar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(
        threadId ? { pregunta, thread_id: threadId } : { pregunta },
      ),
      signal,
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") {
      throw e;
    }
    throw new Error("Could not connect to the server.");
  }

  if (res.status === 422) {
    throw new Error("Invalid question.");
  }

  if (!res.ok) {
    const cuerpo = (await res.json().catch(() => null)) as {
      detail?: string;
    } | null;
    throw new Error(cuerpo?.detail ?? "Server error.");
  }

  return (await res.json()) as ConsultaResponse;
}

export async function exportar(
  sql: string,
  formato: "csv" | "xlsx",
): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${BASE}/v1/exportar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sql, formato }),
    });
  } catch {
    throw new Error("Could not connect to the server.");
  }
  if (!res.ok) {
    const cuerpo = (await res.json().catch(() => null)) as {
      detail?: string;
    } | null;
    throw new Error(cuerpo?.detail ?? "Could not generate file.");
  }
  const blob = await res.blob();
  const disposition = res.headers.get("Content-Disposition") ?? "";
  const match = /filename="?([^";]+)"?/.exec(disposition);
  const nombreArchivo = match?.[1] ?? `export.${formato}`;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nombreArchivo;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
