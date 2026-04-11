// Raw shape returned by CMS API
export interface CMSFacility {
  provnum: string;
  provname: string;
  address: string;
  city: string;
  state: string;
  zip: string;
  latitude: string;
  longitude: string;
  overall_rating: string;
  quality_rating: string;
  staffing_rating: string;
  health_inspection_rating: string;
  reported_rn_staffing_hours_per_resident_per_day: string;
  reported_total_nurse_staffing_hours_per_resident_per_day: string;
  number_of_deficiencies: string;
  total_weighted_health_survey_score: string;
}

// Stored in D1
export interface Facility {
  cms_id: string;
  name: string;
  address: string;
  city: string;
  state: string;
  zip: string;
  latitude: number;
  longitude: number;
  overall_rating: number;
  quality_rating: number;
  staffing_rating: number;
  inspection_rating: number;
  rn_hours_per_resident_day: number;
  total_deficiencies: number;
  grade_score: number;
  grade_letter: string;
  grade_summary: string;
  slug: string;
  updated_at: string;
}

// Cloudflare Worker environment bindings
export interface Env {
  DB: D1Database;
  CACHE: KVNamespace;
}
