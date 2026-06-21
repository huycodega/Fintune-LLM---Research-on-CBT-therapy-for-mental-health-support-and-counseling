export const RISK_LEVELS = [
  { value: "", label: "All" },
  { value: "L0", label: "L0" },
  { value: "L1", label: "L1" },
  { value: "L2", label: "L2" },
  { value: "L3", label: "L3" },
];

export const RISK_META = {
  L0: { label: "L0 - Crisis", short: "L0", tone: "l3" },
  L1: { label: "L1 - High risk", short: "L1", tone: "l3" },
  L2: { label: "L2 - Moderate", short: "L2", tone: "l2" },
  L3: { label: "L3 - Routine", short: "L3", tone: "l0" },
};

export const CHECKLIST_ITEMS = [
  { key: "empathy", label: "Empathy" },
  { key: "noDiagnosis", label: "No diagnosis" },
  { key: "cbtSuggestion", label: "CBT suggestion" },
  { key: "safeResponse", label: "Safe response" },
  { key: "escalationNeeded", label: "Escalation needed" },
];
