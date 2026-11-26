"use client"
import type { ParetoPoint } from "../lib/types"

export type Series = { label: string; color: string; points: ParetoPoint[]; line?: boolean }

/** Accuracy (y) vs. parameters (x) scatter in SVG; axis ranges fit the supplied data. */
export function Scatter({ series, title }: { series: Series[]; title: string }) {
  const all = series.flatMap((item) => item.points)
  if (all.length === 0) return null
  const width = 640, height = 340, pad = 48
  const xs = all.map((p) => p.params_m), ys = all.map((p) => p.validation_accuracy)
  const [x0, x1] = [Math.min(...xs), Math.max(...xs)]; const [y0, y1] = [Math.min(...ys), Math.max(...ys)]
  const sx = (v: number) => pad + ((v - x0) / (x1 - x0 || 1)) * (width - pad * 2)
  const sy = (v: number) => height - pad - ((v - y0) / (y1 - y0 || 1)) * (height - pad * 2)
  return <figure className="chart"><svg role="img" aria-label={title} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="xMidYMid meet">
    <line x1={pad} y1={height - pad} x2={width - pad} y2={height - pad} stroke="#3a4a66" /><line x1={pad} y1={pad} x2={pad} y2={height - pad} stroke="#3a4a66" />
    <text x={width / 2} y={height - 10} textAnchor="middle" fontSize="11" fill="#8fa3c2">parameters (millions) — minimize</text>
    <text x={14} y={height / 2} textAnchor="middle" fontSize="11" fill="#8fa3c2" transform={`rotate(-90 14 ${height / 2})`}>validation accuracy (%) — maximize</text>
    {[x0, x1].map((v) => <text key={`x${v}`} x={sx(v)} y={height - pad + 14} textAnchor="middle" fontSize="10" fill="#8fa3c2">{v.toFixed(2)}</text>)}
    {[y0, y1].map((v) => <text key={`y${v}`} x={pad - 6} y={sy(v) + 3} textAnchor="end" fontSize="10" fill="#8fa3c2">{v.toFixed(1)}</text>)}
    {series.map((item) => <g key={item.label}>
      {item.line ? <polyline fill="none" stroke={item.color} strokeWidth={1.5} points={[...item.points].sort((a, b) => a.params_m - b.params_m).map((p) => `${sx(p.params_m)},${sy(p.validation_accuracy)}`).join(" ")} /> : null}
      {item.points.map((p) => <circle key={`${item.label}-${p.index}`} cx={sx(p.params_m)} cy={sy(p.validation_accuracy)} r={item.line ? 2.5 : 4} fill={item.color}><title>{`#${p.index}: ${p.validation_accuracy.toFixed(2)}% · ${p.params_m.toFixed(3)}M`}</title></circle>)}
    </g>)}
  </svg><figcaption>{series.map((item) => <span key={item.label}><i style={{ background: item.color }} />{item.label}</span>)}</figcaption></figure>
}
