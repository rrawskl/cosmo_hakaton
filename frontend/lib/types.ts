export type Interval = {
  start: string;
  end: string;
  state: string;
  metric?: string;
  value?: number;
  unit?: string;
};
export type Factor = {
  mechanism: string;
  status: string;
  rule: string;
  intervals: Interval[];
  facts: Record<string, unknown>[];
  confidence: string;
  confidence_reasons: string[];
  limitations: string[];
  evidence_ids: string[];
  adverse_minutes: number;
  attention_minutes: number;
  shadow_minutes?: number;
  catalog_result?: string;
};
export type WindowResult = {
  start: string;
  end: string;
  duration_minutes: number;
  factors: Factor[];
};
export type Source = {
  id: string;
  provider: string;
  product: string;
  status: string;
  last_success: string | null;
  error: string | null;
  mode: string;
  url: string;
};
export type Evidence = {
  raw_id: string;
  provider: string;
  product: string;
  url: string;
  retrieved_at: string;
  published_at: string | null;
  sha256: string;
  parser_version: string;
  raw_url: string;
  stale: boolean;
};
export type Orbit = {
  epoch: string;
  age_hours: number;
  source: string;
  retrieved_at: string;
  geometry_mode: string;
  coordinates: string;
  limitations: string[];
  points: {
    time: string;
    lat: number;
    lon: number;
    altitude_km: number;
    shadow: boolean;
  }[];
};
export type Result = {
  protons?: import("../app/ProtonPanel").ProtonData | null;
  warnings_status?: string;
  warnings?: {
    event_id: string;
    value: string;
    published_at: string;
    start: string | null;
    end: string | null;
    stale: boolean;
  }[];
  observations?: {
    metric: string;
    value: number;
    unit: string;
    start: string;
    stale: boolean;
  }[];
  id: string;
  created_at: string;
  algorithm_version: string;
  request: {
    mode: string;
    start_utc: string;
    duration_minutes: number;
    search_horizon_minutes: number;
    cutoff_utc: string | null;
  };
  windows: WindowResult[];
  recommendation: { status: string; winner: number | null; reason: string };
  orbit: Orbit | null;
  evidence: Evidence[];
  limitations: string[];
  status: string;
  sources: Source[];
  context: Record<string, unknown>[];
};
