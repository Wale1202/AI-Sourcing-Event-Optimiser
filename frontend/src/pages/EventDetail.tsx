import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { createBid, listBids } from '../api/bids'
import { describeError } from '../api/client'
import { getEvent } from '../api/events'
import { createSupplier, listSuppliers } from '../api/suppliers'
import Badge from '../components/Badge'
import Button from '../components/Button'
import Card from '../components/Card'
import ErrorBanner from '../components/ErrorBanner'
import Input from '../components/Input'
import PageHeader from '../components/PageHeader'
import Spinner from '../components/Spinner'
import type { Bid, SourcingEvent, Supplier } from '../types'

const EMPTY_SUPPLIER = {
  name: '',
  country: '',
  risk_score: '0.2',
  sustainability_score: '70',
}

const EMPTY_BID = {
  supplier_id: '',
  unit_price: '',
  capacity: '',
  lead_time_days: '14',
  quality_score: '80',
}

export default function EventDetail() {
  const { id } = useParams<{ id: string }>()
  const eventId = Number(id)
  const navigate = useNavigate()

  const [event, setEvent] = useState<SourcingEvent | null>(null)
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [bids, setBids] = useState<Bid[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    const [e, s, b] = await Promise.all([
      getEvent(eventId),
      listSuppliers(),
      listBids(eventId),
    ])
    setEvent(e)
    setSuppliers(s)
    setBids(b)
  }, [eventId])

  useEffect(() => {
    setLoading(true)
    refresh()
      .catch((err) => setError(describeError(err)))
      .finally(() => setLoading(false))
  }, [refresh])

  // ---- supplier form ----
  const [supplierForm, setSupplierForm] = useState(EMPTY_SUPPLIER)
  const [supplierError, setSupplierError] = useState<string | null>(null)
  const [supplierSubmitting, setSupplierSubmitting] = useState(false)

  const updateSupplier =
    (key: keyof typeof supplierForm) =>
    (e: React.ChangeEvent<HTMLInputElement>) =>
      setSupplierForm((prev) => ({ ...prev, [key]: e.target.value }))

  const handleAddSupplier = async (e: React.FormEvent) => {
    e.preventDefault()
    setSupplierError(null)
    setSupplierSubmitting(true)
    try {
      await createSupplier({
        name: supplierForm.name.trim(),
        country: supplierForm.country.trim(),
        risk_score: parseFloat(supplierForm.risk_score),
        sustainability_score: parseFloat(supplierForm.sustainability_score),
      })
      setSupplierForm(EMPTY_SUPPLIER)
      await refresh()
    } catch (err) {
      setSupplierError(describeError(err))
    } finally {
      setSupplierSubmitting(false)
    }
  }

  // ---- bid form ----
  const [bidForm, setBidForm] = useState(EMPTY_BID)
  const [bidError, setBidError] = useState<string | null>(null)
  const [bidSubmitting, setBidSubmitting] = useState(false)

  const updateBid =
    (key: keyof typeof bidForm) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
      setBidForm((prev) => ({ ...prev, [key]: e.target.value }))

  const handleAddBid = async (e: React.FormEvent) => {
    e.preventDefault()
    setBidError(null)
    setBidSubmitting(true)
    try {
      await createBid({
        event_id: eventId,
        supplier_id: parseInt(bidForm.supplier_id, 10),
        unit_price: parseFloat(bidForm.unit_price),
        capacity: parseInt(bidForm.capacity, 10),
        lead_time_days: parseInt(bidForm.lead_time_days, 10),
        quality_score: parseFloat(bidForm.quality_score),
      })
      setBidForm({ ...EMPTY_BID, supplier_id: '' })
      await refresh()
    } catch (err) {
      setBidError(describeError(err))
    } finally {
      setBidSubmitting(false)
    }
  }

  const supplierById = useMemo(
    () => new Map(suppliers.map((s) => [s.id, s])),
    [suppliers],
  )

  if (loading) {
    return (
      <Card className="p-8">
        <Spinner label="Loading event…" />
      </Card>
    )
  }

  if (error || !event) {
    return <ErrorBanner message={error ?? 'Event not found.'} />
  }

  return (
    <>
      <PageHeader
        title={event.name}
        subtitle={`${event.category} • ${event.total_demand.toLocaleString()} units`}
        actions={
          <>
            <Button variant="secondary" onClick={() => navigate('/')}>
              ← Back
            </Button>
            <Button
              onClick={() => navigate(`/events/${event.id}/optimise`)}
              disabled={bids.length === 0}
            >
              Run optimisation
            </Button>
          </>
        }
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <ConstraintTile label="Max suppliers" value={event.max_suppliers.toString()} />
        <ConstraintTile
          label="Min quality"
          value={event.min_quality_score.toString()}
        />
        <ConstraintTile
          label="Max average risk"
          value={event.max_average_risk.toString()}
        />
        <ConstraintTile label="Bids on file" value={bids.length.toString()} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* ---- Suppliers ---- */}
        <Card>
          <div className="px-5 py-4 border-b border-slate-200">
            <h2 className="font-semibold text-slate-900">Suppliers</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Suppliers are shared across all events.
            </p>
          </div>
          <form
            onSubmit={handleAddSupplier}
            className="px-5 py-4 border-b border-slate-200 grid grid-cols-2 gap-3"
          >
            <Input
              label="Name"
              value={supplierForm.name}
              onChange={updateSupplier('name')}
              required
            />
            <Input
              label="Country"
              value={supplierForm.country}
              onChange={updateSupplier('country')}
              required
            />
            <Input
              label="Risk score (0–1)"
              type="number"
              min={0}
              max={1}
              step="0.01"
              value={supplierForm.risk_score}
              onChange={updateSupplier('risk_score')}
              required
            />
            <Input
              label="Sustainability (0–100)"
              type="number"
              min={0}
              max={100}
              step="0.1"
              value={supplierForm.sustainability_score}
              onChange={updateSupplier('sustainability_score')}
              required
            />
            {supplierError && (
              <div className="col-span-2">
                <ErrorBanner
                  message={supplierError}
                  onDismiss={() => setSupplierError(null)}
                />
              </div>
            )}
            <div className="col-span-2 flex justify-end">
              <Button type="submit" size="sm" disabled={supplierSubmitting}>
                {supplierSubmitting ? 'Adding…' : 'Add supplier'}
              </Button>
            </div>
          </form>
          <SupplierTable suppliers={suppliers} />
        </Card>

        {/* ---- Bids ---- */}
        <Card>
          <div className="px-5 py-4 border-b border-slate-200">
            <h2 className="font-semibold text-slate-900">Bids on this event</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              One bid per (event, supplier) pair.
            </p>
          </div>
          <form
            onSubmit={handleAddBid}
            className="px-5 py-4 border-b border-slate-200 grid grid-cols-2 gap-3"
          >
            <div className="col-span-2 flex flex-col gap-1">
              <label className="text-sm font-medium text-slate-700">Supplier</label>
              <select
                required
                value={bidForm.supplier_id}
                onChange={updateBid('supplier_id')}
                className="rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm
                           focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              >
                <option value="">Select a supplier…</option>
                {suppliers.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} ({s.country})
                  </option>
                ))}
              </select>
            </div>
            <Input
              label="Unit price"
              type="number"
              min={0.01}
              step="0.01"
              value={bidForm.unit_price}
              onChange={updateBid('unit_price')}
              required
            />
            <Input
              label="Capacity"
              type="number"
              min={1}
              value={bidForm.capacity}
              onChange={updateBid('capacity')}
              required
            />
            <Input
              label="Lead time (days)"
              type="number"
              min={0}
              value={bidForm.lead_time_days}
              onChange={updateBid('lead_time_days')}
              required
            />
            <Input
              label="Quality score (0–100)"
              type="number"
              min={0}
              max={100}
              step="0.1"
              value={bidForm.quality_score}
              onChange={updateBid('quality_score')}
              required
            />
            {bidError && (
              <div className="col-span-2">
                <ErrorBanner
                  message={bidError}
                  onDismiss={() => setBidError(null)}
                />
              </div>
            )}
            <div className="col-span-2 flex justify-end">
              <Button
                type="submit"
                size="sm"
                disabled={bidSubmitting || suppliers.length === 0}
              >
                {bidSubmitting ? 'Adding…' : 'Add bid'}
              </Button>
            </div>
          </form>
          <BidTable bids={bids} supplierById={supplierById} />
        </Card>
      </div>
    </>
  )
}

function ConstraintTile({ label, value }: { label: string; value: string }) {
  return (
    <Card className="px-4 py-3">
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-lg font-semibold text-slate-900 tabular-nums">
        {value}
      </p>
    </Card>
  )
}

function SupplierTable({ suppliers }: { suppliers: Supplier[] }) {
  if (suppliers.length === 0) {
    return (
      <p className="px-5 py-6 text-sm text-slate-500">No suppliers yet.</p>
    )
  }
  return (
    <table className="w-full text-sm">
      <thead className="bg-slate-50 text-slate-600">
        <tr className="text-left">
          <th className="px-5 py-2 font-medium">Name</th>
          <th className="px-5 py-2 font-medium">Country</th>
          <th className="px-5 py-2 font-medium text-right">Risk</th>
          <th className="px-5 py-2 font-medium text-right">Sustainability</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-slate-100">
        {suppliers.map((s) => (
          <tr key={s.id}>
            <td className="px-5 py-2 font-medium text-slate-900">{s.name}</td>
            <td className="px-5 py-2 text-slate-600">{s.country}</td>
            <td className="px-5 py-2 text-right tabular-nums">
              {s.risk_score.toFixed(2)}
            </td>
            <td className="px-5 py-2 text-right tabular-nums">
              {s.sustainability_score.toFixed(1)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function BidTable({
  bids,
  supplierById,
}: {
  bids: Bid[]
  supplierById: Map<number, Supplier>
}) {
  if (bids.length === 0) {
    return (
      <p className="px-5 py-6 text-sm text-slate-500">
        No bids yet — add at least one before running the optimiser.
      </p>
    )
  }
  return (
    <table className="w-full text-sm">
      <thead className="bg-slate-50 text-slate-600">
        <tr className="text-left">
          <th className="px-5 py-2 font-medium">Supplier</th>
          <th className="px-5 py-2 font-medium text-right">Unit price</th>
          <th className="px-5 py-2 font-medium text-right">Capacity</th>
          <th className="px-5 py-2 font-medium text-right">Lead</th>
          <th className="px-5 py-2 font-medium text-right">Quality</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-slate-100">
        {bids.map((bid) => {
          const supplier = supplierById.get(bid.supplier_id)
          return (
            <tr key={bid.id}>
              <td className="px-5 py-2 font-medium text-slate-900">
                {supplier?.name ?? `Supplier #${bid.supplier_id}`}
                {supplier && (
                  <span className="ml-2 text-xs text-slate-500">
                    {supplier.country}
                  </span>
                )}
              </td>
              <td className="px-5 py-2 text-right tabular-nums">
                {bid.unit_price.toFixed(2)}
              </td>
              <td className="px-5 py-2 text-right tabular-nums">
                {bid.capacity.toLocaleString()}
              </td>
              <td className="px-5 py-2 text-right tabular-nums">
                {bid.lead_time_days}d
              </td>
              <td className="px-5 py-2 text-right">
                <Badge tone={bid.quality_score >= 80 ? 'ok' : 'neutral'}>
                  {bid.quality_score.toFixed(1)}
                </Badge>
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}
