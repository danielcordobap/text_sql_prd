import { useRef, useState } from "react";
import { consultar } from "./api";
import { ChatInput } from "./components/ChatInput";
import { MessageList } from "./components/MessageList";
import type { Turno } from "./types";
import "./styles.css";

export function App() {
  const [mensajes, setMensajes] = useState<Turno[]>([]);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [cargando, setCargando] = useState<boolean>(false);
  const controllerRef = useRef<AbortController | null>(null);

  const manejarEnviar = async (pregunta: string) => {
    if (!pregunta.trim() || cargando) {
      return;
    }

    const nuevoTurnoIndex = mensajes.length;
    setMensajes((prev) => [...prev, { pregunta }]);
    setCargando(true);

    const controller = new AbortController();
    controllerRef.current = controller;

    try {
      const resp = await consultar(
        pregunta,
        threadId ?? undefined,
        controller.signal,
      );
      setMensajes((prev) => {
        const copia = [...prev];
        copia[nuevoTurnoIndex] = {
          pregunta,
          respuesta: resp,
        };
        return copia;
      });
      if (resp.thread_id) {
        setThreadId(resp.thread_id);
      }
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === "AbortError") {
        setMensajes((prev) => {
          const copia = [...prev];
          copia[nuevoTurnoIndex] = { pregunta, cancelado: true };
          return copia;
        });
      } else {
        const mensajeError =
          err instanceof Error
            ? err.message
            : "An unexpected error occurred while processing the query.";
        setMensajes((prev) => {
          const copia = [...prev];
          copia[nuevoTurnoIndex] = {
            pregunta,
            error: mensajeError,
          };
          return copia;
        });
      }
    } finally {
      setCargando(false);
      controllerRef.current = null;
    }
  };

  const manejarCancelar = () => {
    controllerRef.current?.abort();
  };

  return (
    <div className="app-container">
      <header className="app-header">
        <div className="header-top">
          <h1>Text-to-SQL Assistant</h1>
          <div className="header-badges">
            <span
              className="bilingual-badge"
              title="This agent accepts questions in English and Spanish"
            >
              🌐 Bilingual Agent (ES / EN)
            </span>
            {threadId && (
              <span className="thread-badge" title="Conversational session ID">
                Thread: {threadId.substring(0, 8)}...
              </span>
            )}
          </div>
        </div>
        <p className="subtitle">
          Natural language queries to Azure SQL Server with LangGraph
        </p>
      </header>

      <main className="app-main">
        {mensajes.length === 0 ? (
          <div className="empty-state">
            <span className="empty-icon">📊</span>
            <h2>How can I help you today?</h2>
            <p>
              Ask any database query in English or Spanish about sales,
              customers, or products.
            </p>
          </div>
        ) : (
          <MessageList
            mensajes={mensajes}
            cargando={cargando}
            onEnviar={manejarEnviar}
          />
        )}
      </main>

      <footer className="app-footer">
        <ChatInput
          onEnviar={manejarEnviar}
          onCancelar={manejarCancelar}
          cargando={cargando}
        />
      </footer>
    </div>
  );
}

export default App;
