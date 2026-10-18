import { generateDummyPassword } from "./db/utils";

export const isProductionEnvironment = process.env.NODE_ENV === "production";
export const isDevelopmentEnvironment = process.env.NODE_ENV === "development";
export const isTestEnvironment = Boolean(
  process.env.PLAYWRIGHT_TEST_BASE_URL ||
    process.env.PLAYWRIGHT ||
    process.env.CI_PLAYWRIGHT
);

export const guestRegex = /^guest-\d+$/;

export const DUMMY_PASSWORD = generateDummyPassword();

export const suggestedQuestions = [
  { category: "Technical", text: "How do I reset my password?" },
  { category: "Billing", text: "What is the refund policy for annual plans?" },
  { category: "Billing", text: "How do I upgrade or downgrade my plan?" },
  {
    category: "Technical",
    text: "Our API calls return 401 — what should we check?",
  },
];

export const suggestions = suggestedQuestions.map((q) => q.text);
