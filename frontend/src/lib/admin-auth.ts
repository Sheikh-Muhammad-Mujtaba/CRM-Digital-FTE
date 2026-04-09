export const ADMIN_SESSION_KEY = "crm_admin_auth";
export const ADMIN_GATE_COOKIE = "crm_admin_gate";

export type AdminCredentials = {
  username: string;
  password: string;
};

export function saveAdminCredentials(credentials: AdminCredentials): void {
  if (typeof window === "undefined") {
    return;
  }

  // Session cookie is used by Next.js proxy route protection.
  document.cookie = `${ADMIN_GATE_COOKIE}=1; path=/; max-age=28800; samesite=lax`;

  window.sessionStorage.setItem(
    ADMIN_SESSION_KEY,
    window.btoa(JSON.stringify(credentials)),
  );
}

export function getAdminCredentials(): AdminCredentials | null {
  if (typeof window === "undefined") {
    return null;
  }

  const raw = window.sessionStorage.getItem(ADMIN_SESSION_KEY);
  if (!raw) {
    return null;
  }

  try {
    const parsed = JSON.parse(window.atob(raw)) as AdminCredentials;
    if (!parsed.username || !parsed.password) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function clearAdminCredentials(): void {
  if (typeof window === "undefined") {
    return;
  }
  document.cookie = `${ADMIN_GATE_COOKIE}=; path=/; max-age=0; samesite=lax`;
  window.sessionStorage.removeItem(ADMIN_SESSION_KEY);
}
