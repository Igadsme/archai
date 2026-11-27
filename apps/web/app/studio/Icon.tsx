import type { ReactNode } from 'react'

export type IconName =
  | 'overview' | 'generator' | 'explorer' | 'search' | 'training' | 'pareto'
  | 'benchmarks' | 'experiments' | 'registry' | 'system' | 'chevron' | 'play'
  | 'download' | 'filter' | 'zoomIn' | 'zoomOut' | 'fit' | 'more' | 'check'
  | 'copy' | 'terminal' | 'database' | 'gpu' | 'clock' | 'compare' | 'close'
  | 'layers' | 'layout' | 'lock' | 'eye' | 'refresh' | 'alert' | 'key'

const paths: Record<IconName, ReactNode> = {
  overview: <><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></>,
  generator: <><path d="M12 3v18M3 12h18" /><path d="m5.6 5.6 12.8 12.8M18.4 5.6 5.6 18.4" /></>,
  explorer: <><circle cx="5" cy="12" r="2.3" /><circle cx="19" cy="5" r="2.3" /><circle cx="19" cy="19" r="2.3" /><path d="m7.2 11 9.6-5M7.2 13l9.6 5" /></>,
  search: <><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 5 5" /><path d="M8 10.5h5M10.5 8v5" /></>,
  training: <><path d="M3 19V9m6 10V5m6 14v-7m6 7V3" /><path d="m3 8 6-4 6 7 6-9" /></>,
  pareto: <><circle cx="5" cy="17" r="1.5" /><circle cx="9" cy="13" r="1.5" /><circle cx="14" cy="10" r="1.5" /><circle cx="19" cy="5" r="1.5" /><path d="M3 21h18M3 21V3" /></>,
  benchmarks: <><path d="M4 20h16M6 17V9h3v8m3 0V4h3v13m3 0v-5h3v5" /></>,
  experiments: <><path d="M9 3v5l-5 9a2.5 2.5 0 0 0 2.2 3.7h11.6A2.5 2.5 0 0 0 20 17l-5-9V3" /><path d="M8 3h8M7 15h10" /></>,
  registry: <><ellipse cx="12" cy="5" rx="8" ry="3" /><path d="M4 5v7c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12v7c0 1.7 3.6 3 8 3s8-1.3 8-3v-7" /></>,
  system: <><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1a1.7 1.7 0 0 0 1.9.3A1.7 1.7 0 0 0 10 3V2.8h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z" /></>,
  chevron: <path d="m9 18 6-6-6-6" />,
  play: <path d="m8 5 11 7-11 7Z" />,
  download: <><path d="M12 3v13m-5-5 5 5 5-5M4 21h16" /></>,
  filter: <path d="M3 5h18l-7 8v6l-4 2v-8Z" />,
  zoomIn: <><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 5 5M8 10.5h5m-2.5-2.5v5" /></>,
  zoomOut: <><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 5 5M8 10.5h5" /></>,
  fit: <><path d="M8 3H3v5m13-5h5v5M8 21H3v-5m13 5h5v-5" /></>,
  more: <><circle cx="5" cy="12" r="1" fill="currentColor" /><circle cx="12" cy="12" r="1" fill="currentColor" /><circle cx="19" cy="12" r="1" fill="currentColor" /></>,
  check: <path d="m5 12 4 4L19 6" />,
  copy: <><rect x="8" y="8" width="12" height="12" rx="2" /><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2" /></>,
  terminal: <><path d="m4 6 5 5-5 5M11 18h9" /></>,
  database: <><ellipse cx="12" cy="5" rx="8" ry="3" /><path d="M4 5v7c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12v7c0 1.7 3.6 3 8 3s8-1.3 8-3v-7" /></>,
  gpu: <><rect x="3" y="6" width="18" height="12" rx="2" /><circle cx="9" cy="12" r="3" /><path d="M15 10h3m-3 4h3M7 3v3m5-3v3m5-3v3M7 18v3m5-3v3m5-3v3" /></>,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  compare: <><path d="M7 3v18m10-18v18M3 7l4-4 4 4m2 10 4 4 4-4" /></>,
  close: <path d="M6 6l12 12M18 6 6 18" />,
  layers: <><path d="m12 3 9 5-9 5-9-5Z" /><path d="m3 12 9 5 9-5M3 16l9 5 9-5" /></>,
  layout: <><rect x="3" y="3" width="18" height="18" rx="1" /><path d="M8 3v18M8 15h13" /></>,
  lock: <><rect x="5" y="10" width="14" height="11" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3" /></>,
  eye: <><path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z" /><circle cx="12" cy="12" r="2.5" /></>,
  refresh: <><path d="M20 11a8 8 0 1 0-2.3 5.7" /><path d="M20 4v7h-7" /></>,
  alert: <><path d="M12 3 2 20h20Z" /><path d="M12 10v4m0 3v.01" /></>,
  key: <><circle cx="8" cy="15" r="4" /><path d="m11 12 9-9m-4 4 3 3m-6 0 2 2" /></>,
}

export function Icon({ name, size = 17 }: { name: IconName; size?: number }) {
  return <svg className="icon" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>
}
