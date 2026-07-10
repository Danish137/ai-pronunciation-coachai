import axios from "axios";

import { getSessionId } from "./session";
import type { Assessment, CreateAssessmentPayload } from "../types/assessment";

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL;

if (!apiBaseUrl) {
  throw new Error("Missing VITE_API_BASE_URL. Define it in your frontend environment.");
}

const api = axios.create({
  baseURL: apiBaseUrl,
});

api.interceptors.request.use((config) => {
  config.headers["X-Session-Id"] = getSessionId();
  return config;
});

export async function createAssessment(payload: CreateAssessmentPayload) {
  const formData = new FormData();
  formData.append("audio", payload.file);
  formData.append("source_type", payload.sourceType);
  formData.append("consent_accepted", String(payload.consentAccepted));
  formData.append("reference_text", payload.referenceText);

  const { data } = await api.post<Assessment>("/assessment", formData);
  console.debug("API createAssessment response", data);
  return data;
}

export async function fetchHistory() {
  const { data } = await api.get<Assessment[]>("/assessment/history");
  console.debug("API fetchHistory response", data);
  return data;
}

export async function deleteAttempt(id: number) {
  await api.delete(`/assessment/${id}`);
}

export async function deleteHistory() {
  await api.delete("/assessment/history/all");
}
