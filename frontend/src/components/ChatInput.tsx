import { useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";

interface ChatInputProps {
  onEnviar: (pregunta: string) => void;
  onCancelar: () => void;
  cargando: boolean;
}

export function ChatInput({ onEnviar, onCancelar, cargando }: ChatInputProps) {
  const [texto, setTexto] = useState("");

  const manejarEnvio = (e?: FormEvent) => {
    if (e) {
      e.preventDefault();
    }
    const limpio = texto.trim();
    if (!limpio || cargando) {
      return;
    }
    onEnviar(limpio);
    setTexto("");
  };

  const manejarKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      manejarEnvio();
    }
  };

  return (
    <form className="chat-input-form" onSubmit={manejarEnvio}>
      <input
        type="text"
        className="chat-input-text"
        placeholder="Type your database query in English or Spanish..."
        value={texto}
        onChange={(e) => setTexto(e.target.value)}
        onKeyDown={manejarKeyDown}
        disabled={cargando}
      />
      {cargando ? (
        <button
          type="button"
          className="chat-input-button cancel"
          onClick={onCancelar}
          aria-label="Cancel ongoing query"
        >
          Cancel
        </button>
      ) : (
        <button
          type="submit"
          className="chat-input-button"
          disabled={!texto.trim()}
          aria-label="Send query"
        >
          Send
        </button>
      )}
    </form>
  );
}
