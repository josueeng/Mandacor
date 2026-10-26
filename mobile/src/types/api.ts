export const REQUIRED_ANGLES = [15, 25, 45, 75, 105] as const;
export type RequiredAngle = (typeof REQUIRED_ANGLES)[number];

export interface HealthResponse {
  status: 'ok';
  service: 'mandacor';
  version: string;
  api_version: string;
  recovery: 'OK' | 'ERROR';
  recovery_error: string | null;
}

export type FormulaSystem = 'POLIESTER' | 'PU' | 'LACA' | 'ESMALTE_SINTETICO' | 'EPOXI';

export interface FormulaProductSummary {
  code: string;
  display_code: string;
  description: string;
  year: string;
  universal_code: string;
  nuance: string;
  manufacturer: string;
  observations: string;
  system: FormulaSystem;
  system_label: string;
  paint_line: string;
  finish_code: string;
  finish_label: string;
  personalized: boolean;
  formula_count: number;
  origin: 'SKYMIX' | 'USER';
  editable: boolean;
  reading_count: number;
}

export interface FormulaComponent {
  position: number;
  base_code: string;
  base_name: string;
  weight_g: string;
}

export interface FormulaVariant {
  formula_id: number;
  condition: string;
  package: string;
  version: number;
  updated_at: string;
  total_weight_g: string;
  components: FormulaComponent[];
}

export interface FormulaProduct extends FormulaProductSummary {
  variants: FormulaVariant[];
}

export interface FormulaSearchResult {
  items: FormulaProductSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface FormulaSpectralMatch extends FormulaProductSummary {
  compatibility: number;
  delta_e: number;
  matched_reading_id: string;
  matched_measurement_id: number;
}

export interface FormulaSpectralMatchResult {
  items: FormulaSpectralMatch[];
  total_compared: number;
}

export interface FormulaSearchFilters {
  manufacturer?: string;
  year?: string;
  finish?: string;
  universalCode?: string;
}

export interface FormulaComponentPayload {
  base_code: string;
  base_name: string;
  weight_g: string;
}

export interface FormulaVariantPayload {
  condition: string;
  package: string;
  version: number;
  components: FormulaComponentPayload[];
}

export interface FormulaUpsertPayload {
  code: string;
  description: string;
  year: string;
  universal_code: string;
  nuance: string;
  manufacturer: string;
  observations: string;
  system: FormulaSystem;
  finish_label: string;
  variants: FormulaVariantPayload[];
}

export type MetallicGrain = 'FINO' | 'MEDIO_FINO' | 'MEDIO' | 'GROSSEIRO' | 'MUITO_GROSSEIRO';

export interface FormulaReading {
  reading_id: string;
  product_code: string;
  display_code: string;
  description: string;
  session_id: string;
  measurement_role: 'target' | 'sample';
  formula_id: number | null;
  metallic_grain: MetallicGrain | null;
  notes: string;
  measurement_id: number;
  measurement_guid: string | null;
  instrument_serial: string;
  angles: LabAngle[];
  created_at: string;
  schema_version: number;
  measurement_fingerprint: string | null;
  quality_status: 'eligible' | 'review' | 'legacy_unverified';
  quality_issues: string[];
  capture_context: {
    color_space?: 'CIELAB';
    angles_degrees?: RequiredAngle[];
    illuminant?: string | null;
    observer?: string | null;
    measurement_geometry?: string | null;
  };
}

export type RemoteState = 'ONLINE' | 'OFFLINE' | 'UNKNOWN';

export interface InstrumentInfo {
  manufacturer: string;
  model: string;
  serial: string;
  firmware: string;
  ip: string;
}

export interface DiscoveredInstrument {
  manufacturer: string;
  model: string | null;
  serial: string | null;
  host: string;
  tcp_port: number;
  udp_port: number;
  source: string;
}

export interface InstrumentStatus {
  connected: boolean;
  instrument: InstrumentInfo | null;
}

export interface ConnectResponse extends InstrumentStatus {
  state: 'CONNECTED' | 'MULTIPLE_INSTRUMENTS';
  instruments: DiscoveredInstrument[];
}

export interface LabAngle {
  angle: RequiredAngle;
  l: number;
  a: number;
  b: number;
}

export interface Measurement {
  measurement_id: number;
  guid: string | null;
  timestamp: string | null;
  timestamp_raw: string | null;
  name: string | null;
  instrument_serial: string;
  angles: LabAngle[];
}

export type SessionState =
  | 'WAITING_FOR_TARGET'
  | 'TARGET_CAPTURED'
  | 'WAITING_FOR_SAMPLE'
  | 'READY_FOR_COMPARISON';

export interface ColorSession {
  session_id: string;
  state: SessionState;
  instrument_serial: string;
  target: Measurement | null;
  sample: Measurement | null;
}

export type OperationStatus =
  | 'PREPARED'
  | 'WAITING'
  | 'COMPLETED'
  | 'TIMED_OUT'
  | 'CANCELLED'
  | 'FAILED';

export interface CaptureOperation {
  operation_id: string;
  session_id: string;
  type: 'TARGET' | 'SAMPLE' | 'AFTER';
  status: OperationStatus;
  created_at: string;
  measurement_id: number | null;
  error_code: string | null;
}

export interface DeltaAngle {
  angle: RequiredAngle;
  delta_l: number;
  delta_a: number;
  delta_b: number;
  delta_e76: number;
}

export interface Comparison {
  convention: 'SAMPLE_MINUS_TARGET';
  target_id: number;
  sample_id: number;
  angles: DeltaAngle[];
}

export interface DiagnosisAngle {
  angle: RequiredAngle;
  lightness: string;
  red_green: string;
  yellow_blue: string;
  dominant_axis: string;
  delta_e76: number;
}

export interface DirectionSummary {
  lightness: string;
  red_green: string;
  yellow_blue: string;
}

export interface Diagnosis {
  session_id: string;
  worst_angle: RequiredAngle;
  angles: DiagnosisAngle[];
  front: DirectionSummary;
  mid: DirectionSummary;
  flop: DirectionSummary;
}

export interface CorrectionActions {
  lightness: string;
  red_green: string;
  yellow_blue: string;
}

export interface CorrectionAngle extends CorrectionActions {
  angle: RequiredAngle;
  correction_delta_l: number;
  correction_delta_a: number;
  correction_delta_b: number;
}

export interface CorrectionNeed {
  session_id: string;
  angles: CorrectionAngle[];
  front: CorrectionActions;
  mid: CorrectionActions;
  flop: CorrectionActions;
  global_actions: CorrectionActions;
  global_uniformity: DirectionSummary;
  primary_issue: {
    angle: RequiredAngle;
    group: string;
    axis: string;
    action: string | null;
  };
}

export interface PigmentAssessment {
  angle: RequiredAngle;
  group: string;
  axis: string;
  need: string;
  pigment_effect: string;
}

export interface PigmentCandidate {
  pigment_code: string;
  status: string;
  matched_needs: PigmentAssessment[];
  conflicts: PigmentAssessment[];
  unknown_effects: PigmentAssessment[];
  risks: string[];
  contraindications: string[];
  rationale: string[];
}

export interface PigmentRecommendation {
  candidates: PigmentCandidate[];
  rejected_candidates: PigmentCandidate[];
  warnings: string[];
  requires_bench_test: boolean;
  no_single_safe_candidate: boolean;
  dosage_available: false;
}

export type PaintSystem = 'POLYESTER_BASECOAT' | 'PU' | 'UNKNOWN';
export type FinishType = 'SOLID' | 'METALLIC' | 'PEARL' | 'UNKNOWN';

export type AdjustmentLifecycle =
  | 'PLANNED'
  | 'APPLIED_WAITING_FOR_AFTER'
  | 'COMPLETED'
  | 'CANCELLED_BEFORE_APPLICATION'
  | 'ABANDONED_AFTER_APPLICATION';

export interface AdjustmentComponent {
  pigment_code: string;
  quantity_g: string;
}

export interface AdjustmentCreatePayload {
  system: PaintSystem;
  finish: FinishType;
  volume_ml: string;
  components: AdjustmentComponent[];
  operator_reason: string;
  base_identifier?: string;
  color_description?: string;
}

export interface ObservedResponse {
  angle: RequiredAngle;
  response_l: number;
  response_a: number;
  response_b: number;
}

export interface AdjustmentOutcome {
  angle: RequiredAngle;
  before_delta_e76: number;
  after_delta_e76: number;
  delta_e_improvement: number;
  improvement_l: number;
  lightness_outcome: string;
  improvement_a: number;
  red_green_outcome: string;
  improvement_b: number;
  yellow_blue_outcome: string;
  delta_e_outcome: string;
}

export type TrialVerdict = 'IMPROVED' | 'WORSENED' | 'MIXED' | 'UNCHANGED';
export type AxisChange = 'IMPROVED' | 'UNCHANGED' | 'WORSENED_OVERSHOOT' | 'WORSENED_WRONG_DIRECTION';

export interface AxisAssessment {
  axis: 'L' | 'A' | 'B';
  before_delta: number;
  after_delta: number;
  change: AxisChange;
  crossed_target: boolean;
}

export interface AngleAssessment {
  angle: RequiredAngle;
  before_delta_e76: number;
  after_delta_e76: number;
  change: 'IMPROVED' | 'WORSENED' | 'UNCHANGED';
  axes: AxisAssessment[];
}

export interface TrialAssessment {
  verdict: TrialVerdict;
  worst_delta_e_before: number;
  worst_delta_e_after: number;
  improved_angles: RequiredAngle[];
  worsened_angles: RequiredAngle[];
  overshoot_detected: boolean;
  wrong_direction_detected: boolean;
  delta_e_noise: number;
  axis_noise: number;
  angles: AngleAssessment[];
}

export interface Adjustment {
  adjustment_id: string;
  session_id: string;
  lifecycle: AdjustmentLifecycle;
  target_measurement_id: number;
  before_measurement_id: number;
  after_measurement_id: number | null;
  target: Measurement;
  before: Measurement;
  after: Measurement | null;
  system: PaintSystem;
  finish: FinishType;
  volume_ml: string;
  components: AdjustmentComponent[];
  operator_reason: string;
  observations: string | null;
  created_at: string;
  applied_at: string | null;
  completed_at: string | null;
  learning_eligibility: string;
  dosage_generated_by_system: false;
  observed_response: ObservedResponse[] | null;
  before_comparison: Comparison | null;
  after_comparison: Comparison | null;
  outcomes: AdjustmentOutcome[] | null;
  assessment: TrialAssessment | null;
  operator_disagrees_with_instrument: boolean | null;
  worst_angle_before: RequiredAngle | null;
  worst_angle_after: RequiredAngle | null;
  visual_result: 'BETTER' | 'WORSE' | 'SAME' | 'UNKNOWN' | null;
  operator_status: 'IN_PROGRESS' | 'ACCEPTED' | 'REJECTED' | 'UNKNOWN' | null;
  data_quality_flags: string[] | null;
}
