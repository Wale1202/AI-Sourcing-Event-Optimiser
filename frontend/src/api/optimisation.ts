import type { OptimisationResponse, OptimiseRequest } from '../types'
import { api } from './client'

export const runOptimisation = (
  eventId: number,
  body: OptimiseRequest = {},
) =>
  api
    .post<OptimisationResponse>(`/api/v1/events/${eventId}/optimise`, body)
    .then((r) => r.data)
