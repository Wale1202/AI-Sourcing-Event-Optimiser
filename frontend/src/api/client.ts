import axios, { AxiosError } from 'axios'

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000',
  headers: { 'Content-Type': 'application/json' },
})

/** Turn an axios error into a user-readable message. */
export function describeError(error: unknown): string {
  if (error instanceof AxiosError) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail) && detail.length > 0 && detail[0]?.msg) {
      // FastAPI 422 validation error shape: [{ loc, msg, type }, ...]
      return detail.map((d: { msg: string }) => d.msg).join('; ')
    }
    if (error.message) return error.message
  }
  if (error instanceof Error) return error.message
  return 'Unexpected error'
}
