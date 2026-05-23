// Shapes mirror the Pydantic schemas in backend/app/schemas.py.

export interface SourcingEvent {
  id: number
  name: string
  category: string
  total_demand: number
  max_suppliers: number
  min_quality_score: number
  max_average_risk: number
  created_at: string
}

export interface SourcingEventCreate {
  name: string
  category: string
  total_demand: number
  max_suppliers: number
  min_quality_score: number
  max_average_risk: number
}

export interface Supplier {
  id: number
  name: string
  country: string
  risk_score: number
  sustainability_score: number
}

export interface SupplierCreate {
  name: string
  country: string
  risk_score: number
  sustainability_score: number
}

export interface Bid {
  id: number
  event_id: number
  supplier_id: number
  unit_price: number
  capacity: number
  lead_time_days: number
  quality_score: number
}

export interface BidCreate {
  event_id: number
  supplier_id: number
  unit_price: number
  capacity: number
  lead_time_days: number
  quality_score: number
}

export interface SupplierAllocation {
  supplier_id: number
  supplier_name: string
  awarded_quantity: number
  unit_price: number
  total_cost: number
}

export interface OptimisationResponse {
  status: 'optimal' | 'infeasible' | string
  event_id: number
  result_id: number | null
  allocations: SupplierAllocation[]
  total_cost: number
  average_quality: number
  average_risk: number
  explanation: string
  warnings: string[]
}

export interface ExtractedField {
  value: number | string
  confidence: 'high' | 'medium' | 'low' | string
  matched_text: string
}

export interface BriefParseResponse {
  original_text: string
  category: ExtractedField | null
  total_demand: ExtractedField | null
  max_suppliers: ExtractedField | null
  min_quality_score: ExtractedField | null
  risk_preference: ExtractedField | null
  cost_priority: ExtractedField | null
  confidence_notes: string[]
  missing_fields: string[]
}
