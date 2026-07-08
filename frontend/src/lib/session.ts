const SESSION_STORAGE_KEY = "pronounceai-session-id";

function generateId() {
  return crypto.randomUUID();
}

export function getSessionId() {
  const existing = window.localStorage.getItem(SESSION_STORAGE_KEY);
  if (existing) {
    return existing;
  }

  const next = generateId();
  window.localStorage.setItem(SESSION_STORAGE_KEY, next);
  return next;
}
