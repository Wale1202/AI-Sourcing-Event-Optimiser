import type { OptimisationResponse } from '../types'
import { api } from './client'

export const runOptimisation = (eventId: number) =>
  api
    .post<OptimisationResponse>(`/api/v1/events/${eventId}/optimise`)
    .then((r) => r.data)
