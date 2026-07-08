// Minimal typed API client with JWT handling.
const BASE = "/api/v1";

export function getToken(): string | null {
  return localStorage.getItem("access_token");
}

export async function login(email: string, password: string): Promise<void> {
  const body = new URLSearchParams({ username: email, password });
  const res = await fetch(`${BASE}/auth/login`, { method: "POST", body });
  if (!res.ok) throw new Error("Invalid email or password");
  const data = await res.json();
  localStorage.setItem("access_token", data.access_token);
  localStorage.setItem("refresh_token", data.refresh_token);
}

export function logout(): void {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${getToken() ?? ""}`,
      ...(init.headers ?? {}),
    },
  });
  if (res.status === 401) {
    logout();
    window.location.href = "/login";
    throw new Error("Session expired");
  }
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.status === 204 ? (undefined as T) : res.json();
}

export interface Zone {
  id: number; camera_id: number; name: string; type: string; polygon: number[][];
}
export interface Camera {
  id: number; name: string; source: string; type: string; status: string;
  location: string; fps_target: number; is_active: boolean; measured_fps: number;
  zones: Zone[];
}
export interface Overview {
  total_visitors_today: number; current_occupancy: number; avg_dwell_s: number;
  max_queue_length: number; active_cameras: number; open_alerts: number;
}
export interface Alert {
  id: number; camera_id: number | null; ts: string; type: string;
  severity: string; message: string; acknowledged: boolean;
}
export interface TrafficPoint { ts: string; count: number; }
export interface Identity {
  id: number; first_seen: string; last_seen: string; track_count: number;
}
export interface JourneyTrack {
  camera_id: number; track_id: number; first_seen: string; last_seen: string;
  trajectory: number[][]; zones_visited: string[];
}
export interface IdentityJourney { identity: Identity; tracks: JourneyTrack[]; }
