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

// --- Structured explanation pieces ---

export interface SelectedRationale {
  supplier_id: number
  supplier_name: string
  awarded_quantity: number
  rationale: string
  reason_codes: string[]
}

export interface RejectedRationale {
  supplier_id: number
  supplier_name: string
  unit_price: number | null
  quality_score: number | null
  capacity: number | null
  reason: string
  reason_code: string
}

export interface BindingConstraintReport {
  name: string
  description: string
}

export interface TradeOff {
  summary: string
  impact: 'high' | 'medium' | 'low' | string
}

export interface StructuredExplanation {
  headline: string
  selected: SelectedRationale[]
  rejected: RejectedRationale[]
  binding_constraints: BindingConstraintReport[]
  primary_constraint: BindingConstraintReport | null
  trade_offs: TradeOff[]
}

// --- Per-run overrides + request body ---

export interface ConstraintOverrides {
  max_suppliers?: number
  min_quality_score?: number
  max_average_risk?: number
}

export interface OptimiseRequest {
  label?: string | null
  overrides?: ConstraintOverrides | null
}

// --- Live run response ---

export interface OptimisationResponse {
  status: 'optimal' | 'infeasible' | string
  event_id: number
  result_id: number | null
  label: string | null
  constraints_used: Record<string, number>
  allocations: SupplierAllocation[]
  total_cost: number
  average_quality: number
  average_risk: number
  average_sustainability: number
  suppliers_selected: number
  explanation: string
  structured_explanation: StructuredExplanation | null
  warnings: string[]
}

// --- Persisted runs (scenario comparison) ---

export interface OptimisationRunSummary {
  id: number
  event_id: number
  label: string | null
  status: string
  total_cost: number
  average_quality: number
  average_risk: number
  average_sustainability: number
  suppliers_selected: number
  constraints_used: Record<string, number>
  created_at: string
}

export interface OptimisationRunDetail extends OptimisationRunSummary {
  allocations: SupplierAllocation[]
  structured_explanation: StructuredExplanation | null
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
