import React, { useState } from "react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  Label,
} from "recharts";
import type { AggregationType, ChartSpec, ChartType, Fila } from "../chart";
import {
  esColumnaMes,
  formatearMes,
  procesarDatosGrafico,
  specPorDefecto,
} from "../chart";

interface ChartPanelProps {
  columnas: string[];
  filas: Fila[];
}

const COLORS = [
  "#3b82f6",
  "#10b981",
  "#f59e0b",
  "#ef4444",
  "#8b5cf6",
  "#ec4899",
  "#14b8a6",
  "#6366f1",
];

// Custom Tooltip component with glassmorphism dark theme and Month legend
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const CustomTooltip: React.FC<any> = ({ active, payload, label, xCol }) => {
  if (!active || !payload || payload.length === 0) return null;

  const isMonth = esColumnaMes(xCol);
  const formattedHeader = isMonth ? formatearMes(label, "en") : String(label);
  const legendPrefix = isMonth ? "Month:" : `${xCol}:`;

  return (
    <div className="custom-chart-tooltip">
      <div className="tooltip-header">
        <span className="tooltip-legend-label">{legendPrefix}</span>{" "}
        <span className="tooltip-header-val">{formattedHeader}</span>
      </div>
      <div className="tooltip-body">
        {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          payload.map((item: any, index: number) => (
            <div key={`item-${index}`} className="tooltip-item">
              <span
                className="tooltip-color-dot"
                style={{ backgroundColor: item.color || item.fill }}
              />
              <span className="tooltip-item-name">{item.name}:</span>
              <span className="tooltip-item-val">
                {typeof item.value === "number"
                  ? item.value.toLocaleString()
                  : item.value}
              </span>
            </div>
          ))
        }
      </div>
    </div>
  );
};

export const ChartPanel: React.FC<ChartPanelProps> = ({ columnas, filas }) => {
  const [spec, setSpec] = useState<ChartSpec>(() =>
    specPorDefecto(columnas, filas),
  );

  const [showTitleEditor, setShowTitleEditor] = useState<boolean>(false);

  if (!filas || filas.length === 0 || !spec.xCol) {
    return (
      <div className="chart-panel chart-panel-empty">
        <p>No data available to display chart.</p>
      </div>
    );
  }

  const handleXChange = (newX: string) => {
    setSpec((prev) => {
      let newY = prev.yCol;
      if (newY === newX) {
        const candidate = columnas.find((c) => c !== newX);
        newY = candidate || newX;
      }
      return {
        ...prev,
        xCol: newX,
        yCol: newY,
        tituloEjeX: newX,
        tituloEjeY: newY,
        tituloGrafico: `${newY} by ${newX}`,
      };
    });
  };

  const handleYChange = (newY: string) => {
    setSpec((prev) => ({
      ...prev,
      yCol: newY,
      tituloEjeY: newY,
      tituloGrafico: `${newY} by ${prev.xCol}`,
    }));
  };

  const handleGroupChange = (newGroup: string) => {
    setSpec((prev) => ({
      ...prev,
      groupCol: newGroup === "__none__" ? null : newGroup,
    }));
  };

  const { data, series } = procesarDatosGrafico(filas, spec, "en");

  return (
    <div className="chart-panel">
      <div className="chart-controls">
        <div className="chart-control-group">
          <label htmlFor="chart-type-select">Type:</label>
          <select
            id="chart-type-select"
            value={spec.tipo}
            onChange={(e) =>
              setSpec((prev) => ({
                ...prev,
                tipo: e.target.value as ChartType,
              }))
            }
          >
            <option value="bar">Bar Chart</option>
            <option value="line">Line Chart</option>
            <option value="pie">Pie Chart</option>
          </select>
        </div>

        <div className="chart-control-group">
          <label htmlFor="chart-x-select">X Axis:</label>
          <select
            id="chart-x-select"
            value={spec.xCol}
            onChange={(e) => handleXChange(e.target.value)}
          >
            {columnas.map((col) => (
              <option key={col} value={col}>
                {col}
              </option>
            ))}
          </select>
        </div>

        <div className="chart-control-group">
          <label htmlFor="chart-y-select">Y Axis:</label>
          <select
            id="chart-y-select"
            value={spec.yCol}
            onChange={(e) => handleYChange(e.target.value)}
          >
            {columnas.map((col) => (
              <option key={col} value={col}>
                {col}
              </option>
            ))}
          </select>
        </div>

        {spec.tipo !== "pie" && (
          <div className="chart-control-group">
            <label htmlFor="chart-group-select">Group By (Legend):</label>
            <select
              id="chart-group-select"
              value={spec.groupCol || "__none__"}
              onChange={(e) => handleGroupChange(e.target.value)}
            >
              <option value="__none__">None (Sin agrupar)</option>
              {columnas
                .filter((c) => c !== spec.xCol)
                .map((col) => (
                  <option key={col} value={col}>
                    {col}
                  </option>
                ))}
            </select>
          </div>
        )}

        <div className="chart-control-group">
          <label htmlFor="chart-agg-select">Aggregation:</label>
          <select
            id="chart-agg-select"
            value={spec.agg}
            onChange={(e) =>
              setSpec((prev) => ({
                ...prev,
                agg: e.target.value as AggregationType,
              }))
            }
          >
            <option value="sum">Sum (Suma)</option>
            <option value="avg">Average (Promedio)</option>
            <option value="count">Count (Conteo)</option>
            <option value="max">Max (Máximo)</option>
            <option value="min">Min (Mínimo)</option>
            <option value="raw">Raw (Sin agregar)</option>
          </select>
        </div>

        <div className="chart-control-group">
          <button
            type="button"
            className="chart-edit-titles-btn"
            onClick={() => setShowTitleEditor((prev) => !prev)}
          >
            ✏️ {showTitleEditor ? "Close Titles Editor" : "Edit Titles"}
          </button>
        </div>

        {spec.tipo === "bar" && spec.groupCol && series.length >= 2 && (
          <div className="chart-control-group">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={spec.stacked}
                onChange={(e) =>
                  setSpec((prev) => ({ ...prev, stacked: e.target.checked }))
                }
              />
              Stacked Bars
            </label>
          </div>
        )}
      </div>

      {showTitleEditor && (
        <div className="chart-title-editor-panel">
          <div className="editor-input-group">
            <label htmlFor="edit-chart-title">Chart Title:</label>
            <input
              id="edit-chart-title"
              type="text"
              value={spec.tituloGrafico || ""}
              onChange={(e) =>
                setSpec((prev) => ({ ...prev, tituloGrafico: e.target.value }))
              }
              placeholder="Main Title"
            />
          </div>
          <div className="editor-input-group">
            <label htmlFor="edit-x-title">X Axis Label:</label>
            <input
              id="edit-x-title"
              type="text"
              value={spec.tituloEjeX || ""}
              onChange={(e) =>
                setSpec((prev) => ({ ...prev, tituloEjeX: e.target.value }))
              }
              placeholder="X Axis Label"
            />
          </div>
          <div className="editor-input-group">
            <label htmlFor="edit-y-title">Y Axis Label:</label>
            <input
              id="edit-y-title"
              type="text"
              value={spec.tituloEjeY || ""}
              onChange={(e) =>
                setSpec((prev) => ({ ...prev, tituloEjeY: e.target.value }))
              }
              placeholder="Y Axis Label"
            />
          </div>
        </div>
      )}

      {spec.tituloGrafico && (
        <h3 className="chart-main-title">{spec.tituloGrafico}</h3>
      )}

      <div className="chart-container" style={{ width: "100%", height: 350 }}>
        <ResponsiveContainer width="100%" height="100%">
          {spec.tipo === "bar" ? (
            <BarChart
              data={data}
              margin={{ top: 20, right: 30, left: 35, bottom: 30 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="name" stroke="#9ca3af">
                {spec.tituloEjeX && (
                  <Label
                    value={spec.tituloEjeX}
                    position="insideBottom"
                    offset={-15}
                    style={{ fill: "#9ca3af", fontSize: 12, fontWeight: 600 }}
                  />
                )}
              </XAxis>
              <YAxis stroke="#9ca3af">
                {spec.tituloEjeY && (
                  <Label
                    value={spec.tituloEjeY}
                    angle={-90}
                    position="insideLeft"
                    offset={-20}
                    style={{
                      fill: "#9ca3af",
                      fontSize: 12,
                      fontWeight: 600,
                      textAnchor: "middle",
                    }}
                  />
                )}
              </YAxis>
              <Tooltip content={<CustomTooltip xCol={spec.xCol} />} />
              <Legend wrapperStyle={{ paddingTop: "10px" }} />
              {series.map((s, index) => (
                <Bar
                  key={s}
                  dataKey={s}
                  fill={COLORS[index % COLORS.length]}
                  stackId={spec.stacked ? "stack" : undefined}
                  radius={[4, 4, 0, 0]}
                />
              ))}
            </BarChart>
          ) : spec.tipo === "line" ? (
            <LineChart
              data={data}
              margin={{ top: 20, right: 30, left: 35, bottom: 30 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="name" stroke="#9ca3af">
                {spec.tituloEjeX && (
                  <Label
                    value={spec.tituloEjeX}
                    position="insideBottom"
                    offset={-15}
                    style={{ fill: "#9ca3af", fontSize: 12, fontWeight: 600 }}
                  />
                )}
              </XAxis>
              <YAxis stroke="#9ca3af">
                {spec.tituloEjeY && (
                  <Label
                    value={spec.tituloEjeY}
                    angle={-90}
                    position="insideLeft"
                    offset={-20}
                    style={{
                      fill: "#9ca3af",
                      fontSize: 12,
                      fontWeight: 600,
                      textAnchor: "middle",
                    }}
                  />
                )}
              </YAxis>
              <Tooltip content={<CustomTooltip xCol={spec.xCol} />} />
              <Legend wrapperStyle={{ paddingTop: "10px" }} />
              {series.map((s, index) => (
                <Line
                  key={s}
                  type="monotone"
                  dataKey={s}
                  stroke={COLORS[index % COLORS.length]}
                  strokeWidth={2.5}
                  dot={{ r: 4, fill: COLORS[index % COLORS.length] }}
                  activeDot={{ r: 6 }}
                />
              ))}
            </LineChart>
          ) : (
            <PieChart margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
              <Tooltip content={<CustomTooltip xCol={spec.xCol} />} />
              <Legend />
              <Pie
                data={data}
                dataKey={spec.yCol}
                nameKey="name"
                cx="50%"
                cy="50%"
                outerRadius={100}
                label
              >
                {data.map((_entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={COLORS[index % COLORS.length]}
                  />
                ))}
              </Pie>
            </PieChart>
          )}
        </ResponsiveContainer>
      </div>
    </div>
  );
};
