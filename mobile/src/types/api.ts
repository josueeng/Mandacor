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
  worst_angle_before: RequiredAngle | null;
  worst_angle_after: RequiredAngle | null;
  visual_result: 'BETTER' | 'WORSE' | 'SAME' | 'UNKNOWN' | null;
  operator_status: 'IN_PROGRESS' | 'ACCEPTED' | 'REJECTED' | 'UNKNOWN' | null;
  data_quality_flags: string[] | null;
}
