import type { Bid, BidCreate } from '../types'
import { api } from './client'

export const listBids = (eventId?: number) => {
  const params = eventId !== undefined ? { event_id: eventId } : undefined
  return api.get<Bid[]>('/api/v1/bids', { params }).then((r) => r.data)
}

export const createBid = (payload: BidCreate) =>
  api.post<Bid>('/api/v1/bids', payload).then((r) => r.data)

export const deleteBid = (id: number) =>
  api.delete(`/api/v1/bids/${id}`).then(() => undefined)
