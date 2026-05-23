import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { describeError } from '../api/client'
import { listEvents } from '../api/events'
import Badge from '../components/Badge'
import Button from '../components/Button'
import Card from '../components/Card'
import ErrorBanner from '../components/ErrorBanner'
import PageHeader from '../components/PageHeader'
import Spinner from '../components/Spinner'
import type { SourcingEvent } from '../types'

export default function Dashboard() {
  const navigate = useNavigate()
  const [events, setEvents] = useState<SourcingEvent[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listEvents()
      .then(setEvents)
      .catch((e) => setError(describeError(e)))
  }, [])

  return (
    <>
      <PageHeader
        title="Sourcing Events"
        subtitle="All sourcing events in this workspace."
        actions={
          <>
            <Button variant="secondary" onClick={() => navigate('/briefs')}>
              Use Brief Assistant
            </Button>
            <Button onClick={() => navigate('/events/new')}>+ New event</Button>
          </>
        }
      />

      {error && (
        <div className="mb-4">
          <ErrorBanner message={error} onDismiss={() => setError(null)} />
        </div>
      )}

      {events === null && !error && (
        <Card className="p-8">
          <Spinner label="Loading events…" />
        </Card>
      )}

      {events !== null && events.length === 0 && (
        <Card className="p-12 text-center">
          <p className="text-slate-700 font-medium mb-1">No sourcing events yet</p>
          <p className="text-slate-500 text-sm mb-6">
            Create one manually or draft it from a free-text brief.
          </p>
          <div className="flex items-center justify-center gap-2">
            <Button variant="secondary" onClick={() => navigate('/briefs')}>
              Use Brief Assistant
            </Button>
            <Button onClick={() => navigate('/events/new')}>+ New event</Button>
          </div>
        </Card>
      )}

      {events !== null && events.length > 0 && (
        <Card>
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr className="text-left">
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Category</th>
                <th className="px-4 py-3 font-medium text-right">Demand</th>
                <th className="px-4 py-3 font-medium text-right">Max suppliers</th>
                <th className="px-4 py-3 font-medium text-right">Min quality</th>
                <th className="px-4 py-3 font-medium text-right">Max avg risk</th>
                <th className="px-4 py-3 font-medium">Created</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {events.map((event) => (
                <tr key={event.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium text-slate-900">
                    {event.name}
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone="info">{event.category}</Badge>
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {event.total_demand.toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {event.max_suppliers}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {event.min_quality_score}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {event.max_average_risk}
                  </td>
                  <td className="px-4 py-3 text-slate-500">
                    {new Date(event.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Link
                      to={`/events/${event.id}`}
                      className="text-indigo-600 hover:text-indigo-800 font-medium"
                    >
                      Open →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </>
  )
}
