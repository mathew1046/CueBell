export type Preference = 'visual' | 'vibration' | 'sound';
export type Intent = {
  intent: string; context: string | null; token: string | null;
  alert_preferences: Preference[]; clarification: string | null;
};
export type Rule = {
  id: string; token: string; status: string; alert_preferences: Preference[];
};
export type QueueAlert = {
  id: string; token: string; counter: string | null;
  state: 'unacknowledged' | 'acknowledged' | 'corrected';
  acknowledged?: boolean;
  alert_preferences: Preference[];
};
export type QueueEvent = {
  type: string; sequence?: number; at?: number; state?: string; message?: string;
  mode?: string; rule?: Rule; alert?: QueueAlert;
  segment?: { id: string; text: string; received_at: number };
  observation?: { id: string; type: string; token_normalized: string | null;
    counter: string | null; evidence_text: string; ambiguity_reason: string | null };
};
export type Connection = { url: string; token: string; expires: number; suppressMonitor?: boolean };
export type NativeSnapshot = {
  running: boolean; state: string; message: string; mode: string; events: QueueEvent[];
};
