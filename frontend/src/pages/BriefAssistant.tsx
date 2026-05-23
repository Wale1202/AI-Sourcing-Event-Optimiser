import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { parseBrief } from '../api/briefs'
import { describeError } from '../api/client'
import Badge from '../components/Badge'
import Button from '../components/Button'
import Card from '../components/Card'
import ErrorBanner from '../components/ErrorBanner'
import PageHeader from '../components/PageHeader'
import Spinner from '../components/Spinner'
import type {
  BriefParseResponse,
  ExtractedField,
  SourcingEventCreate,
} from '../types'

const EXAMPLE_BRIEF =
  'We need 1000 laptops for Q3. Prioritise low cost, but avoid high-risk ' +
  'suppliers. I want at most 3 suppliers and quality should be at least 75.'

const FIELD_LABELS: Record<
  keyof Pick<
    BriefParseResponse,
    | 'category'
    | 'total_demand'
    | 'max_suppliers'
    | 'min_quality_score'
    | 'risk_preference'
    | 'cost_priority'
  >,
  string
> = {
  category: 'Category',
  total_demand: 'Total demand',
  max_suppliers: 'Max suppliers',
  min_quality_score: 'Min quality score',
  risk_preference: 'Risk preference',
  cost_priority: 'Cost priority',
}

function confidenceTone(c: string): 'ok' | 'warn' | 'neutral' {
  if (c === 'high') return 'ok'
  if (c === 'medium') return 'warn'
  return 'neutral'
}

function deriveMaxRisk(pref: ExtractedField | null): number {
  if (pref?.value === 'avoid_high_risk') return 0.3
  if (pref?.value === 'risk_tolerant') return 0.7
  return 0.5
}

function buildDraft(result: BriefParseResponse): Partial<SourcingEventCreate> {
  return {
    name: '',
    category:
      typeof result.category?.value === 'string'
        ? result.category.value
        : undefined,
    total_demand:
      typeof result.total_demand?.value === 'number'
        ? result.total_demand.value
        : undefined,
    max_suppliers:
      typeof result.max_suppliers?.value === 'number'
        ? result.max_suppliers.value
        : undefined,
    min_quality_score:
      typeof result.min_quality_score?.value === 'number'
        ? result.min_quality_score.value
        : undefined,
    max_average_risk: deriveMaxRisk(result.risk_preference),
  }
}

export default function BriefAssistant() {
  const navigate = useNavigate()
  const [text, setText] = useState(EXAMPLE_BRIEF)
  const [parsing, setParsing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<BriefParseResponse | null>(null)

  const handleParse = async () => {
    setError(null)
    setParsing(true)
    try {
      const r = await parseBrief(text)
      setResult(r)
    } catch (err) {
      setError(describeError(err))
    } finally {
      setParsing(false)
    }
  }

  const handleCreateFromDraft = () => {
    if (!result) return
    navigate('/events/new', { state: buildDraft(result) })
  }

  return (
    <>
      <PageHeader
        title="Sourcing Brief Assistant"
        subtitle="Paste a plain-English brief. We extract a draft — you confirm before anything is created."
      />

      <Card className="p-5 mb-6 bg-amber-50 border-amber-200">
        <p className="text-sm text-amber-900">
          <strong>Assistant, not agent.</strong> This view drafts structured
          fields from your brief — it never creates an event or runs the
          optimiser on its own. Always review the extracted values before
          proceeding.
        </p>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="p-5">
          <label
            htmlFor="brief-text"
            className="block text-sm font-medium text-slate-700 mb-2"
          >
            Brief
          </label>
          <textarea
            id="brief-text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={10}
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm
                       focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            placeholder="e.g. We need 500 office chairs by end of year..."
          />
          {error && (
            <div className="mt-3">
              <ErrorBanner message={error} onDismiss={() => setError(null)} />
            </div>
          )}
          <div className="flex items-center justify-between mt-4">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setText(EXAMPLE_BRIEF)}
              disabled={parsing}
            >
              Reset to example
            </Button>
            <Button onClick={handleParse} disabled={parsing || text.trim().length === 0}>
              {parsing ? 'Parsing…' : 'Parse brief'}
            </Button>
          </div>
        </Card>

        <Card className="p-5">
          <h2 className="font-semibold text-slate-900 mb-3">Extracted draft</h2>
          {parsing && <Spinner label="Parsing…" />}
          {!parsing && !result && (
            <p className="text-sm text-slate-500">
              Run the parser to see extracted fields and any information the
              buyer still needs to fill in.
            </p>
          )}
          {result && <ExtractionPanel result={result} onCreate={handleCreateFromDraft} />}
        </Card>
      </div>
    </>
  )
}

function ExtractionPanel({
  result,
  onCreate,
}: {
  result: BriefParseResponse
  onCreate: () => void
}) {
  const entries = (
    Object.keys(FIELD_LABELS) as (keyof typeof FIELD_LABELS)[]
  ).map((key) => ({
    key,
    label: FIELD_LABELS[key],
    value: result[key],
  }))

  return (
    <div className="space-y-5">
      <dl className="divide-y divide-slate-100 border border-slate-200 rounded-md">
        {entries.map(({ key, label, value }) => (
          <div
            key={key}
            className="px-4 py-3 grid grid-cols-3 gap-2 items-start"
          >
            <dt className="text-sm font-medium text-slate-600">{label}</dt>
            <dd className="col-span-2 text-sm">
              {value ? (
                <div className="flex flex-col gap-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-slate-900">
                      {String(value.value)}
                    </span>
                    <Badge tone={confidenceTone(value.confidence)}>
                      {value.confidence}
                    </Badge>
                  </div>
                  <span className="text-xs text-slate-500">
                    matched: “{value.matched_text}”
                  </span>
                </div>
              ) : (
                <span className="text-slate-400 italic">not detected</span>
              )}
            </dd>
          </div>
        ))}
      </dl>

      {result.missing_fields.length > 0 && (
        <div>
          <p className="text-sm font-medium text-slate-700 mb-2">
            Still to confirm
          </p>
          <div className="flex flex-wrap gap-1.5">
            {result.missing_fields.map((field) => (
              <Badge key={field} tone="warn">
                {field}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {result.confidence_notes.length > 0 && (
        <details className="text-sm">
          <summary className="cursor-pointer text-slate-600 hover:text-slate-900 font-medium">
            Confidence notes
          </summary>
          <ul className="mt-2 list-disc pl-5 text-slate-600 space-y-1">
            {result.confidence_notes.map((note, i) => (
              <li key={i}>{note}</li>
            ))}
          </ul>
        </details>
      )}

      <div className="flex justify-end pt-2 border-t border-slate-100">
        <Button onClick={onCreate}>Create event from draft →</Button>
      </div>
    </div>
  )
}
