import { adminRequest, query } from "./http.js";
import { mockCases, mockScreenings, mockModerations, mockActivities, mockCharts } from "./mockAdminData.js";

const moderationRows = async () => {
  const data = await adminRequest("/ai-moderation/sessions?limit=6").catch(() => null);
  if (!data?.items) return mockModerations;
  return data.items.map(item => ({
    id: item.id,
    queue_code: item.sessionId,
    user_masked: item.userName || item.userCode,
    risk_level: item.riskLevel,
    status: "pending",
    created_at: item.createdAt,
  }));
};

export const mockDashboardApi = {
  summary: async () => {
    const [users, moderation] = await Promise.all([
      adminRequest("/users/stats").catch(() => ({
        total_users: 3, active_users: 2, high_risk_users: 2,
      })),
      adminRequest("/ai-moderation/stats").catch(() => ({
        totalPending: mockModerations.length,
      })),
    ]);
    return {
      total_users: { value: users.total_users ?? users.totalUsers ?? 3, change_percent: 12.5 },
      active_users: { value: users.active_users ?? users.activeUsers ?? 2, change_percent: 8.2 },
      high_risk_users: { value: users.high_risk_users ?? users.highRiskUsers ?? 2, change_percent: -5 },
      today_screenings: { value: mockScreenings.length, change_percent: 16.7 },
      pending_ai_moderations: { value: moderation.totalPending ?? mockModerations.length, change_percent: -10 },
      open_cases: { value: mockCases.filter(item => item.status !== "closed").length, change_percent: 4.2 },
      published_resources: { value: 6, change_percent: 20 },
      active_cbt_lessons: { value: 4, change_percent: 0 },
      generated_at: new Date().toISOString(),
    };
  },
  charts: async () => mockCharts,
  recentCases: async () => mockCases.filter(item => ["L0", "L1"].includes(item.risk_level)),
  recentScreenings: async () => mockScreenings,
  pendingModerations: moderationRows,
  recentActivities: async () => mockActivities,
};

const liveDashboardApi = {
  summary: (params) => adminRequest("/dashboard/summary" + query(params)),
  charts: (params) => adminRequest("/dashboard/charts" + query(params)),
  recentCases: (params) => adminRequest("/dashboard/recent-cases" + query(params)),
  recentScreenings: (params) => adminRequest("/dashboard/recent-screenings" + query(params)),
  pendingModerations: (params) => adminRequest("/dashboard/pending-moderations" + query(params)),
  recentActivities: (params) => adminRequest("/dashboard/recent-activities" + query(params)),
};

export const dashboardApi =
  import.meta.env.VITE_ADMIN_DATA_MODE === "mock" ? mockDashboardApi : liveDashboardApi;