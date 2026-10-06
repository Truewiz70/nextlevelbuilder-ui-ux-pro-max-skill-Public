// Mirrors the FastAPI response schemas in apps/api/src/app/modules/*/schemas.py.

export interface Page<T> {
  items: T[];
  total: number;
}

export type Role = "viewer" | "admin" | "owner";

export interface User {
  id: string;
  email: string;
  display_name: string;
  role: Role;
}

export interface Tenant {
  id: string;
  slug: string;
  name: string;
  vertical: string;
  timezone: string;
  business_hours: Record<string, unknown>;
  settings: Record<string, unknown>;
  status: string;
  created_at: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  tenant: Tenant;
  user: User;
}

export interface AgentConfig {
  id: string;
  version: number;
  is_active: boolean;
  system_prompt: string;
  first_message: string;
  voice_id: string;
  voice_provider: string;
  voice_model: string;
  language: string;
  qualification: unknown[];
  escalation_policy: Record<string, unknown>;
}

export interface AgentConfigUpdate {
  system_prompt?: string;
  first_message?: string;
  voice_id?: string;
}

export interface Integration {
  provider: string;
  status: string;
  connected: boolean;
}

export interface CallSummary {
  id: string;
  caller_e164: string;
  direction: string;
  started_at: string;
  ended_at: string | null;
  outcome: string | null;
  sentiment: string | null;
  summary: string | null;
}

export interface TranscriptTurn {
  role: string;
  text: string;
}

export interface CallDetail extends CallSummary {
  recording_url: string | null;
  vendor_cost_cents: number;
  llm_cost_cents: number;
  transcript: TranscriptTurn[];
}

export interface Appointment {
  id: string;
  service: string;
  starts_at: string;
  ends_at: string;
  status: string;
  customer_name: string;
  customer_phone: string;
  customer_email: string | null;
  timezone: string;
}

export interface CallbackRequest {
  id: string;
  caller_e164: string;
  reason: string;
  preferred_window: string | null;
  status: string;
}

export interface CrmSync {
  id: string;
  call_id: string | null;
  provider: string;
  status: string;
  attempts: number;
  last_error: string | null;
  created_at: string;
}

export interface AnalyticsSummary {
  window_days: number;
  total_calls: number;
  classified_calls: number;
  calls_by_outcome: Record<string, number>;
  calls_by_sentiment: Record<string, number>;
  booking_rate: number;
  escalation_rate: number;
  daily_call_volume: { date: string; count: number }[];
}
