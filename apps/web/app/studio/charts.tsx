"use client"

export type Point = { x: number; y: number }
export type LineSeries = { label: string; points: Point[]; variant: "main" | "alt"; area?: boolean; color?: string }

const W = 700
const H = 210
const PAD = 12

function extent(values: number[]): [number, number] {
  const lo = Math.min(...values); const hi = Math.max(...values)
  if (lo === hi) return [lo - 1, hi + 1]
  const margin = (hi - lo) * 0.06
  return [lo - margin, hi + margin]
}

/** Line chart in the Figma "chart-area" style, plotted from measured points only. */
export function LineChart({ series, xLabel, yFormat = (value) => value.toFixed(2), label }: { series: LineSeries[]; xLabel: string; yFormat?: (value: number) => string; label: string }) {
  const all = series.flatMap((item) => item.points)
  if (all.length < 2) return null
  const [x0, x1] = extent(all.map((point) => point.x).concat())
  const [y0, y1] = extent(all.map((point) => point.y))
  const xMin = Math.min(...all.map((point) => point.x)); const xMax = Math.max(...all.map((point) => point.x))
  const sx = (value: number) => ((value - x0) / (x1 - x0)) * W
  const sy = (value: number) => H - PAD - ((value - y0) / (y1 - y0)) * (H - PAD * 2)
  const ticks = [0, 1, 2, 3].map((index) => y1 - ((y1 - y0) * (index + 0.5)) / 4)
  const xTicks = [0, 0.25, 0.5, 0.75, 1].map((fraction) => xMin + (xMax - xMin) * fraction)
  return <div className="chart-area" role="img" aria-label={label}>
    <div className="chart-y">{ticks.map((tick) => <span key={tick}>{yFormat(tick)}</span>)}</div>
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
      <g className="grid-lines"><path d={ticks.map((tick) => `M0 ${sy(tick)}H${W}`).join("")} /></g>
      {series.map((item) => {
        const line = item.points.map((point, index) => `${index ? "L" : "M"}${sx(point.x).toFixed(1)} ${sy(point.y).toFixed(1)}`).join("")
        return <g key={item.label}>
          {item.area && item.points.length > 1 ? <path className="area" d={`${line}V${H}H${sx(item.points[0].x).toFixed(1)}Z`} /> : null}
          <path className={item.variant === "main" ? "line-main" : "line-alt"} d={line} style={item.color ? { stroke: item.color } : undefined} vectorEffect="non-scaling-stroke" />
        </g>
      })}
    </svg>
    <div className="chart-x">{xTicks.map((tick, index) => <span key={index}>{index === xTicks.length - 1 ? `${Math.round(tick)} ${xLabel}` : Math.round(tick)}</span>)}</div>
    <div className="chart-legend">{series.map((item) => <span key={item.label} className={item.variant}><i style={item.color ? { background: item.color } : undefined} /> {item.label}</span>)}</div>
  </div>
}

export type ScatterPoint = { id: string; x: number; y: number; label?: string }
export type ScatterSeries = { label: string; points: ScatterPoint[]; kind: "cloud" | "front" | "reference"; color?: string }

/** Accuracy (y) vs. cost (x) scatter in the Figma "scatter" style; axis ranges fit the data. */
export function ScatterChart({ series, selected, onSelect, xLabel, yLabel, label }: { series: ScatterSeries[]; selected?: string | null; onSelect?: (point: ScatterPoint, series: ScatterSeries) => void; xLabel: string; yLabel: string; label: string }) {
  const all = series.flatMap((item) => item.points)
  if (!all.length) return null
  const width = 760; const height = 310; const left = 44; const right = 740; const top = 20; const bottom = 270
  const [x0, x1] = extent(all.map((point) => point.x))
  const [y0, y1] = extent(all.map((point) => point.y))
  const sx = (value: number) => left + ((value - x0) / (x1 - x0)) * (right - left)
  const sy = (value: number) => bottom - ((value - y0) / (y1 - y0)) * (bottom - top)
  const grid = [0, 1, 2, 3, 4].map((index) => index / 4)
  return <div className="scatter" role="img" aria-label={label}>
    <div className="axis-y">{yLabel}</div>
    <svg viewBox={`0 0 ${width} ${height}`}>
      <g className="grid-lines"><path d={grid.map((f) => `M${left} ${top + f * (bottom - top)}H${right}M${left + f * (right - left)} ${top}V${bottom}`).join("")} /></g>
      {grid.map((f) => <text key={`x${f}`} className="axis-tick" x={left + f * (right - left)} y={bottom + 14} textAnchor="middle">{(x0 + f * (x1 - x0)).toFixed(2)}</text>)}
      {grid.map((f) => <text key={`y${f}`} className="axis-tick" x={left - 5} y={bottom - f * (bottom - top) + 3} textAnchor="end">{(y0 + f * (y1 - y0)).toFixed(1)}</text>)}
      {series.map((item) => {
        const sorted = item.kind === "cloud" ? [] : [...item.points].sort((a, b) => a.x - b.x)
        return <g key={item.label}>
          {sorted.length > 1 ? <path className={item.kind === "front" ? "frontier-line" : "reference-line"} style={item.color ? { stroke: item.color } : undefined} d={sorted.map((point, index) => `${index ? "L" : "M"}${sx(point.x).toFixed(1)} ${sy(point.y).toFixed(1)}`).join("")} /> : null}
          {item.points.map((point) => {
            const isSelected = selected === `${item.label}:${point.id}`
            const r = isSelected ? 7 : item.kind === "cloud" ? 2.5 : 4
            return onSelect && item.kind !== "reference"
              ? <g key={point.id} className={`selectable-dot ${item.kind === "cloud" ? "alt" : ""} ${isSelected ? "selected" : ""}`} role="button" tabIndex={0} aria-label={`${item.label} ${point.label ?? point.id}: ${point.y.toFixed(2)} at ${point.x.toFixed(3)}`}
                  onClick={() => onSelect(point, item)} onKeyDown={(event) => (event.key === "Enter" || event.key === " ") && onSelect(point, item)}>
                  <circle cx={sx(point.x)} cy={sy(point.y)} r={r} style={item.color ? { fill: item.color } : undefined}><title>{`${point.label ?? point.id}: ${point.y.toFixed(2)} · ${point.x.toFixed(3)}`}</title></circle>
                </g>
              : <circle key={point.id} cx={sx(point.x)} cy={sy(point.y)} r={r} className={item.kind === "cloud" ? "scatter-dot" : "pareto-dot"} style={item.color ? { fill: item.color } : undefined}><title>{`${point.label ?? point.id}: ${point.y.toFixed(2)} · ${point.x.toFixed(3)}`}</title></circle>
          })}
        </g>
      })}
    </svg>
    <div className="axis-x">{xLabel}</div>
    <div className="chart-legend scatter-legend">{series.map((item) => <span key={item.label}><i style={item.color ? { background: item.color } : undefined} className={item.kind} /> {item.label}</span>)}</div>
  </div>
}
