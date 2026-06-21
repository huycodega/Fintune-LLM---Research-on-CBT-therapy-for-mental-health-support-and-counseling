export type DashboardMetric = { value: number; change_percent?: number | null };
export type ChartSeries = {
  available: boolean;
  series: Array<Record<string, string | number>>;
};
export interface DashboardSummary {
  total_users: number | DashboardMetric;
  active_users: number | DashboardMetric;
  high_risk_users: number | DashboardMetric;
  today_screenings: number | DashboardMetric;
  pending_ai_moderations: number | DashboardMetric;
  open_cases: number | DashboardMetric;
  published_resources: number | DashboardMetric;
  active_cbt_lessons: number | DashboardMetric;
  attention_required?: Array<Record<string, unknown>>;
  generated_at: string;
}
