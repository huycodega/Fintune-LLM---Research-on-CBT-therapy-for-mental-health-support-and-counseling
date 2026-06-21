export type RiskLevel = "L0" | "L1" | "L2" | "L3";
export type CasePriority = "critical" | "high" | "medium" | "low";
export type CaseStatus =
  | "new" | "viewed" | "assigned" | "monitoring" | "escalated" | "closed";
export interface CaseListItem {
  id: string;
  case_code: string;
  user: { id: string; display_name?: string; email_masked?: string; phone_masked?: string };
  detected_signal_summary?: string;
  priority: CasePriority;
  risk_level: RiskLevel;
  status: CaseStatus;
  assigned_specialist?: { id: string; display_name: string } | null;
  created_at: string;
  version: number;
}
export interface CasePage {
  items: CaseListItem[];
  total: number;
  page: number;
  page_size: number;
}
