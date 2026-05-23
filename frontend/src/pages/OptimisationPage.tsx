import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { describeError } from '../api/client'
import { getEvent } from '../api/events'
import { runOptimisation } from '../api/optimisation'
import Badge from '../components/Badge'
import Button from '../components/Button'
import Card from '../components/Card'
import ErrorBanner from '../components/ErrorBanner'
import PageHeader from '../components/PageHeader'
import Spinner from '../components/Spinner'
import type { OptimisationResponse, SourcingEvent } from '../types'

function formatNumber(value: number, fractionDigits = 2): string {
  return value.toLocaleString('en-US', {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  })
}

export default function OptimisationPage() {
  const { id } = useParams<{ id: string }>()
  const eventId = Number(id)
  const navigate = useNavigate()

  const [event, setEvent] = useState<SourcingEvent | null>(null)
  const [eventError, setEventError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<OptimisationResponse | null>(null)
  const [runError, setRunError] = useState<string | null>(null)

  useEffect(() => {
    getEvent(eventId)
      .then(setEvent)
      .catch((err) => setEventError(describeError(err)))
  }, [eventId])

  const handleRun = async () => {
    setRunError(null)
    setRunning(true)
    try {
      const r = await runOptimisation(eventId)
      setResult(r)
    } catch (err) {
      setRunError(describeError(err))
    } finally {
      setRunning(false)
    }
  }

  if (eventError) {
    return <ErrorBanner message={eventError} />
  }
  if (!event) {
    return (
      <Card className="p-8">
        <Spinner label="Loading event…" />
      </Card>
    )
  }

  return (
    <>
      <PageHeader
        title="Optimisation"
        subtitle={`${event.name} • ${event.total_demand.toLocaleString()} units`}
        actions={
          <>
            <Button
              variant="secondary"
              onClick={() => navigate(`/events/${eventId}`)}
            >
              ← Back to event
            </Button>
            <Button onClick={handleRun} disabled={running}>
              {running ? 'Solving…' : result ? 'Re-run optimisation' : 'Run optimisation'}
            </Button>
          </>
        }
      />

      <Card className="p-5 mb-6">
        <p className="text-sm text-slate-600">
          The solver minimises total cost subject to:
          demand = <strong>{event.total_demand.toLocaleString()}</strong>,
          max suppliers ≤ <strong>{event.max_suppliers}</strong>,
          quality ≥ <strong>{event.min_quality_score}</strong>,
          and quantity-weighted average risk ≤{' '}
          <strong>{event.max_average_risk}</strong>.
        </p>
      </Card>

      {runError && (
        <div className="mb-4">
          <ErrorBanner message={runError} onDismiss={() => setRunError(null)} />
        </div>
      )}

      {running && (
        <Card className="p-8">
          <Spinner label="Solving — this should take well under a second." />
        </Card>
      )}

      {!running && !result && !runError && (
        <Card className="p-8 text-center">
          <p className="text-slate-700 font-medium mb-1">No run yet</p>
          <p className="text-slate-500 text-sm">
            Click <em>Run optimisation</em> above to compute the recommended award.
          </p>
        </Card>
      )}

      {result && <ResultPanel result={result} />}
    </>
  )
}

function ResultPanel({ result }: { result: OptimisationResponse }) {
  const isOptimal = result.status === 'optimal'

  if (!isOptimal) {
    return (
      <Card className="p-6">
        <div className="flex items-center gap-2 mb-3">
          <Badge tone="danger">Infeasible</Badge>
          <span className="text-sm text-slate-600">
            The solver could not satisfy all constraints.
          </span>
        </div>

        {result.warnings.length > 0 && (
          <div className="mb-4">
            <p className="text-sm font-medium text-slate-700 mb-2">Reasons</p>
            <ul className="list-disc pl-5 text-sm text-slate-700 space-y-1">
              {result.warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          </div>
        )}

        <pre className="whitespace-pre-wrap text-xs text-slate-600 bg-slate-50 border border-slate-200 rounded-md p-3">
          {result.explanation}
        </pre>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <SummaryTile label="Status" tone="ok" value="Optimal" />
        <SummaryTile
          label="Total cost"
          value={formatNumber(result.total_cost)}
          mono
        />
        <SummaryTile
          label="Avg quality"
          value={formatNumber(result.average_quality, 2)}
          mono
        />
        <SummaryTile
          label="Avg risk"
          value={formatNumber(result.average_risk, 3)}
          mono
        />
      </div>

      <Card>
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
            {result.allocations.map((a) => (
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

      <Card>
        <div className="px-5 py-4 border-b border-slate-200">
          <h2 className="font-semibold text-slate-900">Why this allocation</h2>
        </div>
        <pre className="whitespace-pre-wrap text-sm text-slate-700 p-5 leading-relaxed">
          {result.explanation}
        </pre>
      </Card>
    </div>
  )
}

function SummaryTile({
  label,
  value,
  tone,
  mono,
}: {
  label: string
  value: string
  tone?: 'ok' | 'warn' | 'danger'
  mono?: boolean
}) {
  return (
    <Card className="px-4 py-3">
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p
        className={`mt-1 text-lg font-semibold text-slate-900 ${
          mono ? 'tabular-nums' : ''
        }`}
      >
        {tone ? <Badge tone={tone}>{value}</Badge> : value}
      </p>
    </Card>
  )
}
