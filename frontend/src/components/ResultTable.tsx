import type { Fila } from "../types";

interface ResultTableProps {
  columnas: string[];
  filas: Fila[];
  truncado: boolean;
  nFilas: number;
}

export function ResultTable({
  columnas,
  filas,
  truncado,
  nFilas,
}: ResultTableProps) {
  if (!columnas.length || !filas.length) {
    return <div className="no-results">No results returned.</div>;
  }

  return (
    <div className="table-container">
      {truncado && (
        <div className="truncado-warning">
          Showing top {nFilas} rows (results truncated by server limit).
        </div>
      )}
      <table className="results-table">
        <thead>
          <tr>
            {columnas.map((col) => (
              <th key={col}>{col}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {filas.map((fila, idx) => (
            <tr key={idx}>
              {columnas.map((col) => (
                <td key={col}>{String(fila[col] ?? "")}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
