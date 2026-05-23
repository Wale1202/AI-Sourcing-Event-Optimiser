import type { SourcingEvent, SourcingEventCreate } from '../types'
import { api } from './client'

export const listEvents = () =>
  api.get<SourcingEvent[]>('/api/v1/events').then((r) => r.data)

export const getEvent = (id: number) =>
  api.get<SourcingEvent>(`/api/v1/events/${id}`).then((r) => r.data)

export const createEvent = (payload: SourcingEventCreate) =>
  api.post<SourcingEvent>('/api/v1/events', payload).then((r) => r.data)

export const deleteEvent = (id: number) =>
  api.delete(`/api/v1/events/${id}`).then(() => undefined)
