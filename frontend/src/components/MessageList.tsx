import type { Turno } from "../types";
import { ResultActions } from "./ResultActions";
import { ResultTable } from "./ResultTable";

interface MessageListProps {
  mensajes: Turno[];
  cargando: boolean;
}

export function MessageList({ mensajes, cargando }: MessageListProps) {
  return (
    <div className="message-list">
      {mensajes.map((turno, idx) => (
        <div key={idx} className="turno-container">
          <div className="user-message">
            <span className="avatar">👤</span>
            <div className="message-content">{turno.pregunta}</div>
          </div>

          {turno.respuesta && (
            <div className="assistant-message">
              <span className="avatar">🤖</span>
              <div className="message-content">
                {turno.respuesta.ok ? (
                  turno.respuesta.tipo === "mensaje" ? (
                    <div className="no-sql-content">
                      {turno.respuesta.mensaje?.split("\n").map((linea, i) => (
                        <p key={i} className="no-sql-paragraph">
                          {linea}
                        </p>
                      ))}
                    </div>
                  ) : (
                    <>
                      <ResultTable
                        columnas={turno.respuesta.columnas}
                        filas={turno.respuesta.filas}
                        truncado={turno.respuesta.truncado}
                        nFilas={turno.respuesta.n_filas}
                      />
                      <ResultActions
                        sql={turno.respuesta.sql}
                        columnas={turno.respuesta.columnas}
                        filas={turno.respuesta.filas}
                      />
                    </>
                  )
                ) : turno.respuesta.codigo_error === "SIN_SQL" ? (
                  <div className="no-sql-content">
                    {turno.respuesta.mensaje?.split("\n").map((linea, i) => (
                      <p key={i} className="no-sql-paragraph">
                        {linea}
                      </p>
                    ))}
                  </div>
                ) : (
                  <div className="error-card">
                    <span className="error-badge">
                      {turno.respuesta.codigo_error ?? "ERROR"}
                    </span>
                    <p className="error-text">
                      {turno.respuesta.mensaje ??
                        `Could not process query (${
                          turno.respuesta.codigo_error ?? "ERROR"
                        }).`}
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}

          {turno.error && (
            <div className="assistant-message error">
              <span className="avatar">⚠️</span>
              <div className="message-content">
                <div className="error-card">
                  <p className="error-text">{turno.error}</p>
                </div>
              </div>
            </div>
          )}

          {turno.cancelado && (
            <div className="assistant-message">
              <span className="avatar">🛑</span>
              <div className="message-content">
                <p className="cancel-note">
                  Cancelled. You stopped waiting; the server may continue
                  processing this query.
                </p>
              </div>
            </div>
          )}
        </div>
      ))}

      {cargando && (
        <div className="assistant-message loading">
          <span className="avatar">🤖</span>
          <div className="message-content">
            <div className="loading-indicator">
              <span className="dot"></span>
              <span className="dot"></span>
              <span className="dot"></span>
              <span className="loading-text">
                Generating and executing SQL query...
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
