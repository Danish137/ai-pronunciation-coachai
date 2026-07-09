export type SourceType = "upload" | "recording";
export type WordStatus = "excellent" | "good" | "watch" | "needs-practice";

export type WordFeedback = {
  word: string;
  score: number;
  status: WordStatus;
  issue: string;
  suggestion: string;
  start_ms: number;
  end_ms: number;
  duration_ms: number;
  error_type: string;
  confidence: "high" | "medium" | "low";
  phoneme_hint: string | null;
  practice_priority: "high" | "medium" | "low";
  ipa: string | null;
  syllables: string[];
  stress_syllable: number | null;
  native_pronunciation: string | null;
  slow_pronunciation: string | null;
  affected_phonemes?: string[];
  affected_syllable?: string | null;
  pronunciation_explanation?: string | null;
  detected_issue_categories?: string[];
  evidence_summary?: string | null;
};

export type CoachOverview = {
  headline: string;
  level_label: string;
  why: string;
  cefr_estimate: string;
  confidence_label: string;
  improvement_potential: string;
  celebration: string;
};

export type CoachSummary = {
  summary: string;
  strengths: string[];
  weaknesses: string[];
  speaking_habits: string[];
  repeated_issue: string;
  advice: string;
};

export type PriorityIssue = {
  word: string;
  score: number;
  why: string;
  likely_issue: string;
  practice_tip: string;
  drill: string;
  difficulty: "easy" | "medium" | "hard";
  priority: "high" | "medium" | "low";
  confidence: "high" | "medium" | "low";
  start_ms: number;
  end_ms: number;
  ipa: string | null;
  syllables: string[];
  stress_syllable: number | null;
  native_pronunciation: string | null;
  slow_pronunciation: string | null;
};

export type PracticeWord = {
  word: string;
  reason: string;
  drill: string;
  syllable_hint: string;
  ipa: string | null;
  stress_syllable: number | null;
  native_pronunciation: string | null;
  slow_pronunciation: string | null;
  repetitions: number;
  estimated_gain: number;
};

export type PracticeSentence = {
  sentence: string;
  focus_words: string[];
};

export type PracticePlan = {
  today_focus: string;
  estimated_score_if_fixed: number;
  estimated_gain: number;
  words: PracticeWord[];
  sentences: PracticeSentence[];
};

export type MetricInsight = {
  key: "overall" | "accuracy" | "prosody" | "fluency" | "completeness";
  label: string;
  score: number;
  band: string;
  explanation: string;
};

export type CoachInsight = {
  title: string;
  value: string;
  description: string;
};

export type Assessment = {
  id: number;
  source_type: SourceType;
  reference_text: string;
  transcript: string;
  overall_score: number;
  accuracy_score: number;
  fluency_score: number;
  prosody_score: number;
  completeness_score: number;
  duration_seconds: number;
  summary: string;
  coaching: string;
  provider_mode: "mock" | "azure";
  word_feedback: WordFeedback[];
  top_issues: PriorityIssue[];
  overview: CoachOverview;
  coach_summary: CoachSummary;
  practice_plan: PracticePlan;
  metrics: MetricInsight[];
  insights: CoachInsight[];
  created_at: string;
};

export type CreateAssessmentPayload = {
  file: File;
  sourceType: SourceType;
  consentAccepted: boolean;
  referenceText: string;
};
