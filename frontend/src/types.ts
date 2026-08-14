export type ConsultaRequest = {
  pregunta: string;
  thread_id?: string;
};

export type Fila = Record<string, unknown>;

export type ConsultaResponse = {
  thread_id: string;
  ok: boolean;
  sql: string | null;
  columnas: string[];
  filas: Fila[];
  n_filas: number;
  truncado: boolean;
  codigo_error: string | null;
  mensaje: string | null;
  tipo: "datos" | "mensaje";
};

export type Turno = {
  pregunta: string;
  respuesta?: ConsultaResponse;
  error?: string;
  cancelado?: boolean;
};
