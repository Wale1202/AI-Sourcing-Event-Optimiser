import type { Supplier, SupplierCreate } from '../types'
import { api } from './client'

export const listSuppliers = () =>
  api.get<Supplier[]>('/api/v1/suppliers').then((r) => r.data)

export const createSupplier = (payload: SupplierCreate) =>
  api.post<Supplier>('/api/v1/suppliers', payload).then((r) => r.data)

export const deleteSupplier = (id: number) =>
  api.delete(`/api/v1/suppliers/${id}`).then(() => undefined)
