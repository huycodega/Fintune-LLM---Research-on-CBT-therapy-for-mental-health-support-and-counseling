export type ScreeningRiskLevel = "L0" | "L1" | "L2" | "L3";
export type ScreeningStatus = "completed" | "pending" | "in_progress" | "expired" | "cancelled";

export interface ScreeningUser {
  id: string;
  full_name: string;
  username?: string;
  email?: string | null;
  phone?: string | null;
  gender?: string | null;
  age?: number | null;
}

export interface ScreeningRecord {
  id: string;
  screening_id: string;
  user_id: string;
  user: ScreeningUser;
  screening_date: string;
  assessment_type: string;
  score: number;
  risk_level: ScreeningRiskLevel;
  status: ScreeningStatus;
  answers: Array<{ question: string; answer: string }>;
  note?: string;
  ai_assessment: {
    risk_summary: string;
    emotions: string[];
    recommendation: string;
  };
  breakdown: { depression: number; anxiety: number; stress: number };
}

export interface ScreeningPage {
  items: ScreeningRecord[];
  total: number;
  page: number;
  page_size: number;
}

export interface ScreeningSummary {
  today: number;
  completion_rate: number;
  high_risk: number;
  high_risk_percent: number;
  average_score: number;
}
