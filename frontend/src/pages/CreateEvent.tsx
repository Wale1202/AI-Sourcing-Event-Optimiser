import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import { describeError } from '../api/client'
import { createEvent } from '../api/events'
import Button from '../components/Button'
import Card from '../components/Card'
import ErrorBanner from '../components/ErrorBanner'
import Input from '../components/Input'
import PageHeader from '../components/PageHeader'
import type { SourcingEventCreate } from '../types'

type DraftFromBrief = Partial<SourcingEventCreate>

function initialFormFromDraft(draft: DraftFromBrief | undefined) {
  return {
    name: draft?.name ?? '',
    category: draft?.category ?? '',
    total_demand: draft?.total_demand?.toString() ?? '',
    max_suppliers: draft?.max_suppliers?.toString() ?? '',
    min_quality_score: draft?.min_quality_score?.toString() ?? '',
    max_average_risk: draft?.max_average_risk?.toString() ?? '0.5',
  }
}

export default function CreateEvent() {
  const navigate = useNavigate()
  const { state } = useLocation()
  const draft = state as DraftFromBrief | undefined

  const [form, setForm] = useState(() => initialFormFromDraft(draft))
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const update =
    (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
      setForm((prev) => ({ ...prev, [key]: e.target.value }))

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      const payload: SourcingEventCreate = {
        name: form.name.trim(),
        category: form.category.trim(),
        total_demand: parseInt(form.total_demand, 10),
        max_suppliers: parseInt(form.max_suppliers, 10),
        min_quality_score: parseFloat(form.min_quality_score),
        max_average_risk: parseFloat(form.max_average_risk),
      }
      const created = await createEvent(payload)
      navigate(`/events/${created.id}`)
    } catch (err) {
      setError(describeError(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <PageHeader
        title="New sourcing event"
        subtitle={
          draft
            ? 'Fields prefilled from your brief — please review and confirm.'
            : 'Define the demand and the constraints the optimiser must respect.'
        }
      />

      <Card className="p-6 max-w-2xl">
        <form className="grid grid-cols-1 md:grid-cols-2 gap-4" onSubmit={handleSubmit}>
          <Input
            label="Event name"
            placeholder="e.g. Q3 Laptop Procurement"
            value={form.name}
            onChange={update('name')}
            required
            className="md:col-span-2"
          />
          <Input
            label="Category"
            placeholder="e.g. IT Hardware"
            value={form.category}
            onChange={update('category')}
            required
            className="md:col-span-2"
          />
          <Input
            label="Total demand"
            type="number"
            min={1}
            value={form.total_demand}
            onChange={update('total_demand')}
            required
            hint="Units to be sourced across all suppliers."
          />
          <Input
            label="Max suppliers"
            type="number"
            min={1}
            value={form.max_suppliers}
            onChange={update('max_suppliers')}
            required
            hint="Cap on the number of awarded suppliers."
          />
          <Input
            label="Min quality score"
            type="number"
            min={0}
            max={100}
            step="0.1"
            value={form.min_quality_score}
            onChange={update('min_quality_score')}
            required
            hint="Bids below this score are excluded."
          />
          <Input
            label="Max average risk"
            type="number"
            min={0}
            max={1}
            step="0.01"
            value={form.max_average_risk}
            onChange={update('max_average_risk')}
            required
            hint="Quantity-weighted ceiling, 0–1."
          />

          {error && (
            <div className="md:col-span-2">
              <ErrorBanner message={error} onDismiss={() => setError(null)} />
            </div>
          )}

          <div className="md:col-span-2 flex items-center justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="secondary"
              onClick={() => navigate(-1)}
              disabled={submitting}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? 'Creating…' : 'Create event'}
            </Button>
          </div>
        </form>
      </Card>
    </>
  )
}
