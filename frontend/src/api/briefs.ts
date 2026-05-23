import type { BriefParseResponse } from '../types'
import { api } from './client'

export const parseBrief = (text: string) =>
  api
    .post<BriefParseResponse>('/api/v1/briefs/parse', { text })
    .then((r) => r.data)
