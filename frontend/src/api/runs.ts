import type { OptimisationRunDetail, OptimisationRunSummary } from '../types'
import { api } from './client'

export const listRunsForEvent = (eventId: number) =>
  api
    .get<OptimisationRunSummary[]>(`/api/v1/events/${eventId}/runs`)
    .then((r) => r.data)

export const getRun = (runId: number) =>
  api.get<OptimisationRunDetail>(`/api/v1/runs/${runId}`).then((r) => r.data)

export const deleteRun = (runId: number) =>
  api.delete(`/api/v1/runs/${runId}`).then(() => undefined)
