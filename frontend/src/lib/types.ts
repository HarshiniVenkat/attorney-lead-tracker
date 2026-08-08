export type LeadState = "PENDING" | "REACHED_OUT";

export type EmailKind = "PROSPECT_CONFIRMATION" | "ATTORNEY_NOTIFICATION";
export type EmailDeliveryStatus = "PENDING" | "SENT" | "FAILED";

export interface ActorSummary {
  id: string;
  full_name: string;
  email: string;
}

export interface Lead {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  state: LeadState;
  created_at: string;
  updated_at: string;
  reached_out_at: string | null;
  reached_out_by: ActorSummary | null;
}

export interface LeadStateEvent {
  id: string;
  from_state: LeadState | null;
  to_state: LeadState;
  created_at: string;
  actor: ActorSummary | null;
}

export interface EmailDelivery {
  id: string;
  kind: EmailKind;
  to_address: string;
  status: EmailDeliveryStatus;
  attempts: number;
  last_error: string | null;
  sent_at: string | null;
  created_at: string;
}

export interface LeadDetail extends Lead {
  resume_filename: string;
  resume_content_type: string;
  resume_size_bytes: number;
  state_events: LeadStateEvent[];
  email_deliveries: EmailDelivery[];
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface CurrentUser {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  created_at: string;
}

/** Mirrors the backend's single error envelope. */
export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details?: {
      fields?: Record<string, string>;
      [key: string]: unknown;
    } | null;
  };
}

export type FieldErrors = Record<string, string>;
