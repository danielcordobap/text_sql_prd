export type ColumnKind = "numeric" | "categorical";
export type ChartType = "bar" | "line" | "pie";
export type AggregationType = "sum" | "avg" | "count" | "max" | "min" | "raw";

export type ChartSpec = {
  tipo: ChartType;
  xCol: string;
  yCol: string;
  groupCol: string | null;
  agg: AggregationType;
  stacked: boolean;
  tituloGrafico?: string;
  tituloEjeX?: string;
  tituloEjeY?: string;
};

export type Fila = Record<string, unknown>;

const MESES_EN = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

const MESES_ES = [
  "Enero",
  "Febrero",
  "Marzo",
  "Abril",
  "Mayo",
  "Junio",
  "Julio",
  "Agosto",
  "Septiembre",
  "Octubre",
  "Noviembre",
  "Diciembre",
];

export function esColumnaMes(colName: string): boolean {
  return /mes|month|sale_month|mes_venta/i.test(colName);
}

export function formatearMes(
  valor: unknown,
  idioma: "es" | "en" = "en",
): string {
  const n = typeof valor === "number" ? valor : parseInt(String(valor), 10);
  if (!isNaN(n) && n >= 1 && n <= 12) {
    const lista = idioma === "es" ? MESES_ES : MESES_EN;
    return lista[n - 1];
  }
  return String(valor ?? "");
}

export function inferirTipoColumna(columna: string, filas: Fila[]): ColumnKind {
  const valores = filas
    .map((f) => f[columna])
    .filter((v) => v !== null && v !== undefined && v !== "");
  if (valores.length === 0) return "categorical";

  const esTemporalODiscreto =
    /fecha|date|\bmes\b|\bmonth\b|sale_month|mes_venta|dia|day|periodo|period/i.test(
      columna,
    );
  if (esTemporalODiscreto) {
    return "categorical";
  }

  const esNumero = (v: unknown) => {
    if (typeof v === "number") return !isNaN(v);
    if (typeof v === "string") {
      const trimmed = v.trim();
      return trimmed !== "" && !isNaN(Number(trimmed));
    }
    return false;
  };

  return valores.every(esNumero) ? "numeric" : "categorical";
}

export function columnasCategoricas(
  columnas: string[],
  filas: Fila[],
): string[] {
  return columnas.filter(
    (col) => inferirTipoColumna(col, filas) === "categorical",
  );
}

export function columnasNumericas(columnas: string[], filas: Fila[]): string[] {
  return columnas.filter((col) => inferirTipoColumna(col, filas) === "numeric");
}

export function esGraficable(columnas: string[], filas: Fila[]): boolean {
  if (!columnas || columnas.length < 2 || !filas || filas.length < 2) {
    return false;
  }
  const numCols = columnasNumericas(columnas, filas);
  const catCols = columnasCategoricas(columnas, filas);
  return numCols.length >= 1 && (catCols.length >= 1 || columnas.length >= 2);
}

export function inferTipoGrafico(
  _columnas: string[],
  filas: Fila[],
  xCol: string,
): ChartType {
  if (!xCol) return "bar";

  const regexTemporal = /fecha|date|año|year|mes|month/i;
  if (regexTemporal.test(xCol)) {
    return "line";
  }

  const valoresDistintos = new Set(
    filas
      .map((f) => f[xCol])
      .filter((v) => v !== null && v !== undefined)
      .map((v) => String(v)),
  );

  if (valoresDistintos.size > 0 && valoresDistintos.size <= 6) {
    return "pie";
  }

  return "bar";
}

function calcularAgregacion(valores: number[], agg: AggregationType): number {
  if (valores.length === 0) return 0;
  if (agg === "raw") return valores[0];
  if (agg === "count") return valores.length;
  if (agg === "max") return Math.max(...valores);
  if (agg === "min") return Math.min(...valores);
  const suma = valores.reduce((acc, v) => acc + v, 0);
  if (agg === "avg") return suma / valores.length;
  return suma; // default "sum"
}

export function procesarDatosGrafico(
  filas: Fila[],
  spec: ChartSpec,
  idioma: "es" | "en" = "en",
): { data: Record<string, unknown>[]; series: string[] } {
  const { xCol, yCol, groupCol, agg } = spec;

  if (!filas || filas.length === 0 || !xCol || !yCol) {
    return { data: [], series: [] };
  }

  const esMes = esColumnaMes(xCol);
  const formatXLabel = (rawVal: unknown) =>
    esMes ? formatearMes(rawVal, idioma) : String(rawVal ?? "");

  // 1. Group By (Series) active
  if (groupCol && groupCol !== xCol) {
    const totalesPorSerie = new Map<string, number>();
    const valoresPorGroupKey = new Map<string, Map<string, number[]>>();

    for (const f of filas) {
      const xRaw = f[xCol];
      const xVal = formatXLabel(xRaw);
      const sRaw = f[groupCol];
      const sVal =
        sRaw !== null && sRaw !== undefined ? String(sRaw) : "(empty)";
      const yVal =
        typeof f[yCol] === "number"
          ? (f[yCol] as number)
          : Number(f[yCol]) || 0;

      totalesPorSerie.set(sVal, (totalesPorSerie.get(sVal) || 0) + yVal);

      if (!valoresPorGroupKey.has(xVal)) {
        valoresPorGroupKey.set(xVal, new Map());
      }
      const mapX = valoresPorGroupKey.get(xVal)!;
      if (!mapX.has(sVal)) {
        mapX.set(sVal, []);
      }
      mapX.get(sVal)!.push(yVal);
    }

    const MAX_SERIES = 12;
    let topSeriesNames: Set<string>;
    let hayOtros = false;

    if (totalesPorSerie.size > MAX_SERIES) {
      const ordenadas = Array.from(totalesPorSerie.entries()).sort(
        (a, b) => b[1] - a[1],
      );
      topSeriesNames = new Set(ordenadas.slice(0, MAX_SERIES).map((e) => e[0]));
      hayOtros = true;
    } else {
      topSeriesNames = new Set(totalesPorSerie.keys());
    }

    const getSeriesKey = (sName: string) =>
      sName === xCol ? `s_${sName}` : sName;

    const finalSeriesList: string[] = Array.from(totalesPorSerie.keys())
      .filter((s) => topSeriesNames.has(s))
      .map(getSeriesKey);

    if (hayOtros) {
      const otrosKey = getSeriesKey("Otros");
      if (!finalSeriesList.includes(otrosKey)) {
        finalSeriesList.push(otrosKey);
      }
    }

    const data: Record<string, unknown>[] = [];
    for (const [xVal, mapX] of valoresPorGroupKey.entries()) {
      const rowObj: Record<string, unknown> = {
        name: xVal,
        [xCol]: xVal,
      };

      const agrupadosSeriesKey = new Map<string, number[]>();

      for (const [sVal, arrY] of mapX.entries()) {
        const keySeries = topSeriesNames.has(sVal)
          ? getSeriesKey(sVal)
          : getSeriesKey("Otros");
        if (!agrupadosSeriesKey.has(keySeries)) {
          agrupadosSeriesKey.set(keySeries, []);
        }
        agrupadosSeriesKey.get(keySeries)!.push(...arrY);
      }

      for (const sKey of finalSeriesList) {
        const arrVals = agrupadosSeriesKey.get(sKey) || [];
        rowObj[sKey] = calcularAgregacion(arrVals, agg);
      }
      data.push(rowObj);
    }

    return { data, series: finalSeriesList };
  }

  // 2. No Group By (Single Metric Y)
  const mapPorX = new Map<string, number[]>();
  for (const f of filas) {
    const xRaw = f[xCol];
    const xVal = formatXLabel(xRaw);
    const yVal =
      typeof f[yCol] === "number" ? (f[yCol] as number) : Number(f[yCol]) || 0;

    if (!mapPorX.has(xVal)) {
      mapPorX.set(xVal, []);
    }
    mapPorX.get(xVal)!.push(yVal);
  }

  const data: Record<string, unknown>[] = [];
  for (const [xVal, arrY] of mapPorX.entries()) {
    data.push({
      name: xVal,
      [xCol]: xVal,
      [yCol]: calcularAgregacion(arrY, agg),
    });
  }

  return { data, series: [yCol] };
}

export function specPorDefecto(columnas: string[], filas: Fila[]): ChartSpec {
  const catCols = columnasCategoricas(columnas, filas);
  const numCols = columnasNumericas(columnas, filas);

  const isTemporalOrDiscreteName = (name: string) =>
    /fecha|date|año|year|\bmes\b|\bmonth\b|sale_month|mes_venta|dia|day|periodo|period|\bid\b|codigo|code/i.test(
      name,
    );

  let xCol = "";
  if (catCols.length > 0) {
    xCol = catCols[0];
  } else {
    const tempCol = columnas.find(isTemporalOrDiscreteName);
    xCol = tempCol || columnas[0] || "";
  }

  let candidateY = numCols.filter((c) => c !== xCol);
  if (candidateY.length === 0) {
    candidateY = columnas.filter((c) => c !== xCol);
  }
  const yCol = candidateY[0] || columnas[0] || "";

  const tipo = inferTipoGrafico(columnas, filas, xCol);

  return {
    tipo,
    xCol,
    yCol,
    groupCol: null,
    agg: "sum",
    stacked: false,
    tituloGrafico: `${yCol} by ${xCol}`,
    tituloEjeX: xCol,
    tituloEjeY: yCol,
  };
}
