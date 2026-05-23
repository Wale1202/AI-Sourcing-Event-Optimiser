import type { ReactNode } from 'react'

type Tone = 'ok' | 'warn' | 'danger' | 'neutral' | 'info'

type Props = {
  tone?: Tone
  children: ReactNode
}

const TONES: Record<Tone, string> = {
  ok: 'bg-green-100 text-green-800 ring-green-200',
  warn: 'bg-amber-100 text-amber-800 ring-amber-200',
  danger: 'bg-red-100 text-red-800 ring-red-200',
  neutral: 'bg-slate-100 text-slate-700 ring-slate-200',
  info: 'bg-indigo-100 text-indigo-800 ring-indigo-200',
}

export default function Badge({ tone = 'neutral', children }: Props) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium
                  ring-1 ring-inset ${TONES[tone]}`}
    >
      {children}
    </span>
  )
}
