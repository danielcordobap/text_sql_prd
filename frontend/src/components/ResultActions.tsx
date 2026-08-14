import React, { Suspense, lazy, useState } from "react";
import type { Fila } from "../chart";
import { exportar } from "../api";
import { esGraficable } from "../chart";

const ChartPanel = lazy(() =>
  import("./ChartPanel").then((m) => ({ default: m.ChartPanel })),
);

interface ResultActionsProps {
  sql: string | null;
  columnas: string[];
  filas: Fila[];
}

export const ResultActions: React.FC<ResultActionsProps> = ({
  sql,
  columnas,
  filas,
}) => {
  const [mostrarGrafico, setMostrarGrafico] = useState(false);
  const [exportando, setExportando] = useState<"csv" | "xlsx" | null>(null);
  const [errorExport, setErrorExport] = useState<string | null>(null);

  const graficable = esGraficable(columnas, filas);
  const puedeExportar = Boolean(sql && filas && filas.length > 0);

  const handleExport = async (formato: "csv" | "xlsx") => {
    if (!sql) return;
    setExportando(formato);
    setErrorExport(null);
    try {
      await exportar(sql, formato);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Error exporting file.";
      setErrorExport(msg);
    } finally {
      setExportando(null);
    }
  };

  const handleDownloadSql = () => {
    if (!sql) return;
    const blob = new Blob([sql], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "query_sql.txt";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="result-actions-container">
      <div className="result-actions-bar">
        {puedeExportar && (
          <>
            <button
              type="button"
              className="action-button export-button"
              disabled={Boolean(exportando)}
              onClick={() => handleExport("csv")}
            >
              {exportando === "csv" ? "Downloading..." : "Download CSV"}
            </button>

            <button
              type="button"
              className="action-button export-button"
              disabled={Boolean(exportando)}
              onClick={() => handleExport("xlsx")}
            >
              {exportando === "xlsx" ? "Downloading..." : "Download Excel"}
            </button>
          </>
        )}

        {sql && (
          <button
            type="button"
            className="action-button export-button"
            aria-label="Download SQL"
            onClick={handleDownloadSql}
          >
            query_sql
          </button>
        )}

        {graficable && (
          <button
            type="button"
            className="action-button chart-toggle-button"
            onClick={() => setMostrarGrafico((prev) => !prev)}
          >
            {mostrarGrafico ? "Hide Chart" : "View Chart"}
          </button>
        )}
      </div>

      {errorExport && (
        <div className="export-error">
          <span>{errorExport}</span>
        </div>
      )}

      {graficable && mostrarGrafico && (
        <Suspense
          fallback={<div className="chart-loading">Loading chart…</div>}
        >
          <ChartPanel columnas={columnas} filas={filas} />
        </Suspense>
      )}
    </div>
  );
};
