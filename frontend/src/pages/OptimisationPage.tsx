import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { describeError } from '../api/client'
import { getEvent } from '../api/events'
import { runOptimisation } from '../api/optimisation'
import { deleteRun, getRun, listRunsForEvent } from '../api/runs'
import Badge from '../components/Badge'
import Button from '../components/Button'
import Card from '../components/Card'
import ErrorBanner from '../components/ErrorBanner'
import Input from '../components/Input'
import PageHeader from '../components/PageHeader'
import Spinner from '../components/Spinner'
import type {
  BindingConstraintReport,
  ConstraintOverrides,
  OptimisationRunDetail,
  OptimisationRunSummary,
  OptimiseRequest,
  RejectedRationale,
  SelectedRationale,
  SourcingEvent,
  StructuredExplanation,
  SupplierAllocation,
  TradeOff,
} from '../types'

function formatNumber(value: number, fractionDigits = 2): string {
  return value.toLocaleString('en-US', {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  })
}

function impactTone(impact: string): 'danger' | 'warn' | 'neutral' {
  if (impact === 'high') return 'danger'
  if (impact === 'medium') return 'warn'
  return 'neutral'
}

function rejectionTone(code: string): 'warn' | 'neutral' {
  if (code === 'quality_floor') return 'warn'
  return 'neutral'
}

const EMPTY_FORM = {
  label: '',
  maxSuppliers: '',
  minQuality: '',
  maxRisk: '',
}

export default function OptimisationPage() {
  const { id } = useParams<{ id: string }>()
  const eventId = Number(id)
  const navigate = useNavigate()

  const [event, setEvent] = useState<SourcingEvent | null>(null)
  const [history, setHistory] = useState<OptimisationRunSummary[]>([])
  const [current, setCurrent] = useState<OptimisationRunDetail | null>(null)

  const [form, setForm] = useState(EMPTY_FORM)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [pageError, setPageError] = useState<string | null>(null)
  const [runError, setRunError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    const [e, h] = await Promise.all([
      getEvent(eventId),
      listRunsForEvent(eventId),
    ])
    setEvent(e)
    setHistory(h)
    return { event: e, history: h }
  }, [eventId])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    refresh()
      .then(async ({ history: h }) => {
        if (cancelled || h.length === 0) return
        const detail = await getRun(h[0].id)
        if (!cancelled) setCurrent(detail)
      })
      .catch((err) => setPageError(describeError(err)))
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [refresh])

  const handleRun = async () => {
    setRunError(null)
    setRunning(true)
    try {
      const overrides: ConstraintOverrides = {}
      if (form.maxSuppliers.trim() !== '')
        overrides.max_suppliers = parseInt(form.maxSuppliers, 10)
      if (form.minQuality.trim() !== '')
        overrides.min_quality_score = parseFloat(form.minQuality)
      if (form.maxRisk.trim() !== '')
        overrides.max_average_risk = parseFloat(form.maxRisk)

      const body: OptimiseRequest = {
        label: form.label.trim() || null,
        overrides: Object.keys(overrides).length > 0 ? overrides : null,
      }
      const response = await runOptimisation(eventId, body)
      await refresh()
      if (response.result_id !== null) {
        const detail = await getRun(response.result_id)
        setCurrent(detail)
      }
      setForm(EMPTY_FORM)
    } catch (err) {
      setRunError(describeError(err))
    } finally {
      setRunning(false)
    }
  }

  const handleSelectRun = async (runId: number) => {
    setPageError(null)
    try {
      const detail = await getRun(runId)
      setCurrent(detail)
    } catch (err) {
      setPageError(describeError(err))
    }
  }

  const handleDeleteRun = async (runId: number) => {
    if (!window.confirm('Delete this saved scenario? It will be removed from history.')) {
      return
    }
    try {
      await deleteRun(runId)
      const { history: refreshed } = await refresh()
      if (current?.id === runId) {
        setCurrent(refreshed.length > 0 ? await getRun(refreshed[0].id) : null)
      }
    } catch (err) {
      setPageError(describeError(err))
    }
  }

  if (loading) {
    return (
      <Card className="p-8">
        <Spinner label="Loading optimisation playground…" />
      </Card>
    )
  }

  if (pageError && !event) {
    return <ErrorBanner message={pageError} />
  }
  if (!event) {
    return <ErrorBanner message="Event not found." />
  }

  return (
    <>
      <PageHeader
        title="Optimisation playground"
        subtitle={`${event.name} • ${event.total_demand.toLocaleString()} units`}
        actions={
          <Button
            variant="secondary"
            onClick={() => navigate(`/events/${eventId}`)}
          >
            ← Back to event
          </Button>
        }
      />

      {pageError && (
        <div className="mb-4">
          <ErrorBanner message={pageError} onDismiss={() => setPageError(null)} />
        </div>
      )}

      <WhatIfForm
        event={event}
        form={form}
        onChange={setForm}
        onSubmit={handleRun}
        running={running}
        error={runError}
        onDismissError={() => setRunError(null)}
      />

      {current && (
        <div className="mt-8">
          <ResultBlock result={current} />
        </div>
      )}

      {history.length > 0 && (
        <div className="mt-8">
          <ScenarioComparison
            history={history}
            currentId={current?.id ?? null}
            onSelect={handleSelectRun}
            onDelete={handleDeleteRun}
          />
        </div>
      )}
    </>
  )
}

// ---------- What-if form ----------

type FormState = typeof EMPTY_FORM

function WhatIfForm({
  event,
  form,
  onChange,
  onSubmit,
  running,
  error,
  onDismissError,
}: {
  event: SourcingEvent
  form: FormState
  onChange: (next: FormState) => void
  onSubmit: () => void
  running: boolean
  error: string | null
  onDismissError: () => void
}) {
  const update =
    (key: keyof FormState) => (e: React.ChangeEvent<HTMLInputElement>) =>
      onChange({ ...form, [key]: e.target.value })

  return (
    <Card className="p-5">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h2 className="font-semibold text-slate-900">Run a scenario</h2>
          <p className="text-sm text-slate-500 mt-0.5">
            Leave override fields blank to use the event defaults. Overrides
            apply only to this run — the event itself isn't changed.
          </p>
        </div>
      </div>

      <Input
        label="Scenario label (optional)"
        placeholder="e.g. Tighter quality floor"
        value={form.label}
        onChange={update('label')}
        className="mb-4 max-w-xl"
      />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Input
          label="Override max suppliers"
          type="number"
          min={1}
          placeholder={event.max_suppliers.toString()}
          value={form.maxSuppliers}
          onChange={update('maxSuppliers')}
          hint={`Event default: ${event.max_suppliers}`}
        />
        <Input
          label="Override min quality score"
          type="number"
          min={0}
          max={100}
          step="0.1"
          placeholder={event.min_quality_score.toString()}
          value={form.minQuality}
          onChange={update('minQuality')}
          hint={`Event default: ${event.min_quality_score}`}
        />
        <Input
          label="Override max average risk"
          type="number"
          min={0}
          max={1}
          step="0.01"
          placeholder={event.max_average_risk.toString()}
          value={form.maxRisk}
          onChange={update('maxRisk')}
          hint={`Event default: ${event.max_average_risk}`}
        />
      </div>

      {error && (
        <div className="mt-4">
          <ErrorBanner message={error} onDismiss={onDismissError} />
        </div>
      )}

      <div className="mt-5 flex justify-end">
        <Button onClick={onSubmit} disabled={running}>
          {running ? 'Solving…' : 'Run optimisation'}
        </Button>
      </div>
    </Card>
  )
}

// ---------- Result block ----------

function ResultBlock({ result }: { result: OptimisationRunDetail }) {
  const isOptimal = result.status === 'optimal'
  const c = result.constraints_used

  return (
    <>
      <Card className="px-5 py-4 mb-4">
        <div className="flex flex-wrap items-center gap-3">
          <Badge tone={isOptimal ? 'ok' : 'danger'}>
            {isOptimal ? 'Optimal' : 'Infeasible'}
          </Badge>
          {result.label && (
            <span className="text-sm font-medium text-slate-900">{result.label}</span>
          )}
          <span className="text-xs text-slate-500">
            {new Date(result.created_at).toLocaleString()}
          </span>
        </div>
        <p className="mt-2 text-xs text-slate-500">
          Constraints used: max suppliers ≤{' '}
          <strong>{c.max_suppliers}</strong>, quality ≥{' '}
          <strong>{c.min_quality_score}</strong>, average risk ≤{' '}
          <strong>{c.max_average_risk}</strong>.
        </p>
      </Card>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
        <MetricTile label="Total cost" value={formatNumber(result.total_cost)} />
        <MetricTile
          label="Suppliers"
          value={result.suppliers_selected.toString()}
        />
        <MetricTile
          label="Avg quality"
          value={formatNumber(result.average_quality)}
        />
        <MetricTile
          label="Avg risk"
          value={formatNumber(result.average_risk, 3)}
        />
        <MetricTile
          label="Avg sustainability"
          value={formatNumber(result.average_sustainability)}
        />
      </div>

      {result.warnings.length > 0 && (
        <Card className="p-4 mb-6 bg-amber-50 border-amber-200">
          <p className="font-medium text-amber-900 mb-2">
            Why this scenario is infeasible
          </p>
          <ul className="list-disc pl-5 space-y-1 text-sm text-amber-900">
            {result.warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </Card>
      )}

      {isOptimal && (
        <>
          <AllocationsCard allocations={result.allocations} />
          {result.structured_explanation && (
            <ExplanationPanels structured={result.structured_explanation} />
          )}
        </>
      )}

      <details className="mt-6">
        <summary className="cursor-pointer text-sm text-slate-600 hover:text-slate-900 font-medium">
          Full explanation text
        </summary>
        <pre className="mt-2 whitespace-pre-wrap text-xs text-slate-700 bg-slate-50 border border-slate-200 rounded-md p-4 leading-relaxed">
          {result.explanation}
        </pre>
      </details>
    </>
  )
}

function MetricTile({ label, value }: { label: string; value: string }) {
  return (
    <Card className="px-4 py-3">
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-lg font-semibold text-slate-900 tabular-nums">
        {value}
      </p>
    </Card>
  )
}

function AllocationsCard({ allocations }: { allocations: SupplierAllocation[] }) {
  return (
    <Card className="mb-6">
      <div className="px-5 py-4 border-b border-slate-200">
        <h2 className="font-semibold text-slate-900">Recommended award</h2>
      </div>
      <table className="w-full text-sm">
        <thead className="bg-slate-50 text-slate-600">
          <tr className="text-left">
            <th className="px-5 py-2 font-medium">Supplier</th>
            <th className="px-5 py-2 font-medium text-right">Quantity</th>
            <th className="px-5 py-2 font-medium text-right">Unit price</th>
            <th className="px-5 py-2 font-medium text-right">Line total</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {allocations.map((a) => (
            <tr key={a.supplier_id}>
              <td className="px-5 py-2 font-medium text-slate-900">
                {a.supplier_name}
              </td>
              <td className="px-5 py-2 text-right tabular-nums">
                {a.awarded_quantity.toLocaleString()}
              </td>
              <td className="px-5 py-2 text-right tabular-nums">
                {formatNumber(a.unit_price)}
              </td>
              <td className="px-5 py-2 text-right tabular-nums font-medium">
                {formatNumber(a.total_cost)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  )
}

// ---------- Explanation panels ----------

function ExplanationPanels({
  structured,
}: {
  structured: StructuredExplanation
}) {
  return (
    <div className="space-y-6">
      <Card className="px-5 py-4 bg-indigo-50 border-indigo-100">
        <p className="text-sm text-indigo-900 font-medium">{structured.headline}</p>
      </Card>

      <SelectedPanel selected={structured.selected} />
      <BindingConstraintsPanel
        binding={structured.binding_constraints}
        primary={structured.primary_constraint}
      />
      <TradeOffsPanel tradeOffs={structured.trade_offs} />
      <RejectedPanel rejected={structured.rejected} />
    </div>
  )
}

function SelectedPanel({ selected }: { selected: SelectedRationale[] }) {
  if (selected.length === 0) return null
  return (
    <Card>
      <div className="px-5 py-4 border-b border-slate-200">
        <h3 className="font-semibold text-slate-900">Why each supplier was selected</h3>
      </div>
      <ul className="divide-y divide-slate-100">
        {selected.map((s) => (
          <li key={s.supplier_id} className="px-5 py-3">
            <div className="flex items-center justify-between gap-3">
              <span className="font-medium text-slate-900">{s.supplier_name}</span>
              <span className="text-sm tabular-nums text-slate-600">
                {s.awarded_quantity.toLocaleString()} units
              </span>
            </div>
            <p className="text-sm text-slate-700 mt-1">{s.rationale}</p>
            {s.reason_codes.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-2">
                {s.reason_codes.map((code) => (
                  <Badge key={code} tone="info">
                    {code.replace(/_/g, ' ')}
                  </Badge>
                ))}
              </div>
            )}
          </li>
        ))}
      </ul>
    </Card>
  )
}

function RejectedPanel({ rejected }: { rejected: RejectedRationale[] }) {
  if (rejected.length === 0) return null
  return (
    <Card>
      <div className="px-5 py-4 border-b border-slate-200">
        <h3 className="font-semibold text-slate-900">
          Why other suppliers were not selected
        </h3>
      </div>
      <table className="w-full text-sm">
        <thead className="bg-slate-50 text-slate-600">
          <tr className="text-left">
            <th className="px-5 py-2 font-medium">Supplier</th>
            <th className="px-5 py-2 font-medium text-right">Unit price</th>
            <th className="px-5 py-2 font-medium text-right">Quality</th>
            <th className="px-5 py-2 font-medium">Reason</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rejected.map((r) => (
            <tr key={r.supplier_id}>
              <td className="px-5 py-2 font-medium text-slate-900">
                {r.supplier_name}
              </td>
              <td className="px-5 py-2 text-right tabular-nums">
                {r.unit_price !== null ? formatNumber(r.unit_price) : '—'}
              </td>
              <td className="px-5 py-2 text-right tabular-nums">
                {r.quality_score !== null ? r.quality_score : '—'}
              </td>
              <td className="px-5 py-2 text-slate-700">
                <div className="flex items-start gap-2">
                  <Badge tone={rejectionTone(r.reason_code)}>
                    {r.reason_code.replace(/_/g, ' ')}
                  </Badge>
                  <span>{r.reason}</span>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  )
}

function BindingConstraintsPanel({
  binding,
  primary,
}: {
  binding: BindingConstraintReport[]
  primary: BindingConstraintReport | null
}) {
  if (binding.length === 0) return null
  return (
    <Card>
      <div className="px-5 py-4 border-b border-slate-200">
        <h3 className="font-semibold text-slate-900">Which constraints shaped the decision</h3>
        {primary && (
          <p className="text-xs text-slate-500 mt-1">
            Most active:{' '}
            <span className="font-medium text-slate-700">{primary.name}</span>
          </p>
        )}
      </div>
      <ul className="divide-y divide-slate-100">
        {binding.map((c) => {
          const isPrimary = primary?.name === c.name
          return (
            <li
              key={c.name}
              className={`px-5 py-3 flex items-start gap-3 ${
                isPrimary ? 'bg-indigo-50' : ''
              }`}
            >
              <Badge tone={isPrimary ? 'info' : 'neutral'}>
                {c.name.replace(/_/g, ' ')}
              </Badge>
              <span className="text-sm text-slate-700">{c.description}</span>
            </li>
          )
        })}
      </ul>
    </Card>
  )
}

function TradeOffsPanel({ tradeOffs }: { tradeOffs: TradeOff[] }) {
  if (tradeOffs.length === 0) return null
  return (
    <Card>
      <div className="px-5 py-4 border-b border-slate-200">
        <h3 className="font-semibold text-slate-900">Trade-offs worth noting</h3>
      </div>
      <ul className="divide-y divide-slate-100">
        {tradeOffs.map((t, i) => (
          <li key={i} className="px-5 py-3 flex items-start gap-3">
            <Badge tone={impactTone(t.impact)}>{t.impact}</Badge>
            <span className="text-sm text-slate-700">{t.summary}</span>
          </li>
        ))}
      </ul>
    </Card>
  )
}

// ---------- Scenario comparison ----------

function ScenarioComparison({
  history,
  currentId,
  onSelect,
  onDelete,
}: {
  history: OptimisationRunSummary[]
  currentId: number | null
  onSelect: (id: number) => void
  onDelete: (id: number) => void
}) {
  return (
    <Card>
      <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
        <div>
          <h2 className="font-semibold text-slate-900">Scenario comparison</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Every run is saved with its constraints + metrics. Click a row to
            view it in detail above.
          </p>
        </div>
        <span className="text-xs text-slate-500 tabular-nums">
          {history.length} run{history.length === 1 ? '' : 's'}
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm min-w-[760px]">
          <thead className="bg-slate-50 text-slate-600">
            <tr className="text-left">
              <th className="px-5 py-2 font-medium">Label</th>
              <th className="px-5 py-2 font-medium">Status</th>
              <th className="px-5 py-2 font-medium text-right">Cost</th>
              <th className="px-5 py-2 font-medium text-right">Suppliers</th>
              <th className="px-5 py-2 font-medium text-right">Quality</th>
              <th className="px-5 py-2 font-medium text-right">Risk</th>
              <th className="px-5 py-2 font-medium text-right">Sustain.</th>
              <th className="px-5 py-2 font-medium">Overrides</th>
              <th className="px-5 py-2" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {history.map((r) => {
              const isCurrent = r.id === currentId
              return (
                <tr
                  key={r.id}
                  className={`cursor-pointer hover:bg-slate-50 ${
                    isCurrent ? 'bg-indigo-50' : ''
                  }`}
                  onClick={() => onSelect(r.id)}
                >
                  <td className="px-5 py-2 font-medium text-slate-900">
                    {r.label ?? <span className="text-slate-400">Untitled</span>}
                    <div className="text-xs text-slate-500 mt-0.5">
                      {new Date(r.created_at).toLocaleString()}
                    </div>
                  </td>
                  <td className="px-5 py-2">
                    <Badge tone={r.status === 'optimal' ? 'ok' : 'danger'}>
                      {r.status}
                    </Badge>
                  </td>
                  <td className="px-5 py-2 text-right tabular-nums">
                    {r.status === 'optimal' ? formatNumber(r.total_cost) : '—'}
                  </td>
                  <td className="px-5 py-2 text-right tabular-nums">
                    {r.suppliers_selected || '—'}
                  </td>
                  <td className="px-5 py-2 text-right tabular-nums">
                    {r.status === 'optimal' ? formatNumber(r.average_quality) : '—'}
                  </td>
                  <td className="px-5 py-2 text-right tabular-nums">
                    {r.status === 'optimal' ? formatNumber(r.average_risk, 3) : '—'}
                  </td>
                  <td className="px-5 py-2 text-right tabular-nums">
                    {r.status === 'optimal' ? formatNumber(r.average_sustainability) : '—'}
                  </td>
                  <td className="px-5 py-2 text-xs text-slate-600">
                    <ConstraintSummary constraints={r.constraints_used} />
                  </td>
                  <td className="px-5 py-2 text-right">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation()
                        onDelete(r.id)
                      }}
                      className="text-xs text-red-600 hover:text-red-800"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

function ConstraintSummary({
  constraints,
}: {
  constraints: Record<string, number>
}) {
  return (
    <div className="space-x-3 whitespace-nowrap">
      <span>≤{constraints.max_suppliers} suppliers</span>
      <span>q≥{constraints.min_quality_score}</span>
      <span>risk≤{constraints.max_average_risk}</span>
    </div>
  )
}
