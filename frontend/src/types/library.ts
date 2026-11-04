export interface UserProfile {
  id: number;
  email: string;
  full_name: string;
  role: 'student' | 'teacher' | 'librarian';
  is_active: boolean;
  created_at: string;
}

export interface Book {
  id: number;
  title: string;
  author: string;
  isbn: string | null;
  category: string;
  description: string | null;
  is_archived: boolean;
  total_copies: number;
  available_copies: number;
  created_at: string;
  updated_at: string;
}

export interface BookCopy {
  id: number;
  book_id: number;
  copy_code: string;
  operational_status: 'available' | 'maintenance' | 'lost' | 'retired';
  is_borrowed: boolean;
  effective_status: string;
  notes: string | null;
  added_at: string;
}

export interface BookDetail extends Book {
  copies: BookCopy[];
}

export interface BookPaginationResponse {
  items: Book[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface Loan {
  id: number;
  student_id: number;
  student_name?: string;
  student_email?: string;
  copy_id: number;
  copy_code: string;
  book_id: number;
  book_title: string;
  book_author: string;
  issued_by_id: number;
  issued_at: string;
  due_date: string;
  returned_at: string | null;
  status: 'active' | 'overdue' | 'returned';
  is_overdue: boolean;
  renewal_count: number;
}

export interface LoanPaginationResponse {
  items: Loan[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface SemanticBookResult {
  id: number;
  title: string;
  author: string;
  isbn: string | null;
  category: string;
  description: string | null;
  total_copies: number;
  available_copies: number;
  similarity_score: number;
}

export interface SemanticSearchResponse {
  items: SemanticBookResult[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  query: string;
  disclaimer: string;
}

export interface HybridBookResult {
  id: number;
  title: string;
  author: string;
  isbn: string | null;
  category: string;
  description: string | null;
  total_copies: number;
  available_copies: number;
  rrf_score: number;
  lexical_rank?: number | null;
  semantic_rank?: number | null;
  similarity_score?: number | null;
  match_channels: string[];
}

export interface HybridSearchResponse {
  items: HybridBookResult[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  total_lexical_matches: number;
  total_semantic_matches: number;
  total_fused_candidates: number;
  query: string;
  applied_category?: string | null;
  model: string;
  fusion_method: string;
}

export interface BookRecommendationResult {
  id: number;
  title: string;
  author: string;
  isbn: string | null;
  category: string;
  description: string | null;
  similarity_score: number;
}

export interface BookRecommendationResponse {
  source_book_id: number;
  source_book_title: string;
  recommendations: BookRecommendationResult[];
  total: number;
  disclaimer: string;
}

export interface EmbeddingStatusResponse {
  total_books: number;
  with_embedding: number;
  missing_embedding: number;
  stale_embedding: number;
  model_name: string;
  model_available: boolean;
  is_processing: boolean;
}

export interface EmbeddingRefreshResponse {
  status: string;
  total_candidates: number;
  processed: number;
  failed: number;
  stale: number;
  missing: number;
  message: string;
  errors?: string[];
}


export interface CopilotSource {
  type: 'book' | 'policy' | 'loan';
  id?: number | null;
  title: string;
  snippet?: string | null;
  author?: string | null;
  category?: string | null;
  available_copies?: number | null;
  total_copies?: number | null;
}

export interface CopilotMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  provider?: string;
  is_fallback?: boolean;
  sources?: CopilotSource[];
  suggested_followups?: string[];
}

export interface CopilotChatResponse {
  reply: string;
  provider: string;
  is_fallback: boolean;
  sources: CopilotSource[];
  suggested_followups: string[];
}


export interface Notification {
  id: number;
  user_id: number;
  loan_id: number | null;
  notification_type: string;
  title: string;
  message: string;
  target_due_date: string | null;
  is_read: boolean;
  created_at: string;
  read_at: string | null;
}

export interface NotificationPaginationResponse {
  items: Notification[];
  total: number;
  unread_count: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface NotificationUnreadCountResponse {
  unread_count: number;
}

export interface PatronProfileUpdate {
  full_name: string;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

export interface StudyZone {
  id: number;
  zone_code: string;
  name: string;
  floor: number;
  total_capacity: number;
  noise_policy: 'silent' | 'quiet' | 'collaborative';
  is_active: boolean;
}

export interface StudySeat {
  id: number;
  zone_id: number;
  seat_code: string;
  has_power_outlet: boolean;
  has_monitor: boolean;
  is_accessible: boolean;
  is_active: boolean;
}

export interface StudyRoom {
  id: number;
  room_code: string;
  name: string;
  capacity: number;
  display_type: 'none' | 'tv' | 'projector';
  has_whiteboard: boolean;
  is_active: boolean;
}

export interface StudySpaceReservation {
  id: number;
  user_id: number;
  resource_type: 'seat' | 'room';
  seat_id: number | null;
  room_id: number | null;
  start_time: string;
  end_time: string;
  status: 'active' | 'completed' | 'cancelled' | 'no_show';
  checked_in_at: string | null;
  expected_attendees: number;
  actual_attendees: number | null;
  created_at: string;
  seat?: StudySeat | null;
  room?: StudyRoom | null;
}

export interface StudySpaceReservationCreate {
  resource_type: 'seat' | 'room';
  seat_id?: number | null;
  room_id?: number | null;
  start_time: string;
  end_time: string;
  expected_attendees?: number;
}

export interface ReservationPaginationResponse {
  items: StudySpaceReservation[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface SpaceAvailabilityResponse {
  start_time: string;
  end_time: string;
  available_seats: StudySeat[];
  available_rooms: StudyRoom[];
}

export interface ReservationQRResponse {
  reservation_id: number;
  qr_token: string;
  expires_at: string;
  start_time: string;
  end_time: string;
  resource_type: 'seat' | 'room';
  resource_name: string;
  checkin_window_start: string;
  checkin_window_end: string;
}

export interface ReservationCheckInRequest {
  actual_attendees?: number | null;
}

export interface ReservationCheckInWithTokenRequest {
  qr_token: string;
  actual_attendees?: number | null;
}

export interface ReservationSweepReport {
  timestamp: string;
  processed_count: number;
  no_show_count: number;
  completed_count: number;
  no_show_reservation_ids: number[];
  completed_reservation_ids: number[];
  execution_duration_ms: number;
}

// ── Stage 10.4: Occupancy Tracking, Telemetry & Analytics ─────────────────────

export interface ZoneOccupancySummary {
  zone_id: number;
  zone_code: string;
  name: string;
  floor: number;
  noise_policy: string;
  total_capacity: number;
  occupied_seats: number;
  available_seats: number;
  utilization_percentage: number;
}

export interface RoomOccupancySummary {
  room_id: number;
  room_code: string;
  name: string;
  capacity: number;
  display_type: string | null;
  has_whiteboard: boolean;
  is_active: boolean;
  is_occupied: boolean;
  current_attendees: number;
  active_reservation_id: number | null;
}

export interface CurrentOccupancyResponse {
  total_library_occupancy: number;
  total_library_capacity: number;
  total_library_available: number;
  overall_utilization_percentage: number;
  occupied_seats: number;
  total_seats: number;
  seat_utilization_percentage: number;
  occupied_room_attendees: number;
  total_room_capacity: number;
  room_attendees_utilization_percentage: number;
  active_rooms_count: number;
  total_rooms_count: number;
  zones: ZoneOccupancySummary[];
  rooms: RoomOccupancySummary[];
  provenance: string;
  as_of: string;
}

export interface ResourceSeatBreakdown {
  total_seats: number;
  occupied_seats: number;
  available_seats: number;
  utilization_percentage: number;
  power_outlet_seats_count: number;
  monitor_seats_count: number;
  accessible_seats_count: number;
}

export interface ResourceRoomBreakdown {
  total_rooms: number;
  active_occupied_rooms: number;
  total_room_capacity: number;
  occupied_room_attendees: number;
  available_room_capacity: number;
  utilization_percentage: number;
  rooms: RoomOccupancySummary[];
}

export interface ResourceOccupancyResponse {
  seats: ResourceSeatBreakdown;
  rooms: ResourceRoomBreakdown;
  provenance: string;
  as_of: string;
}

export interface HistoricalOccupancyDataPoint {
  time_bucket: string;
  zone_id?: number | null;
  avg_observed_count: number;
  max_observed_count: number;
  min_observed_count: number;
  avg_capacity_utilization: number;
  observation_count: number;
}

export interface HistoricalOccupancyResponse {
  interval: 'hour' | 'day';
  zone_id?: number | null;
  start_date: string;
  end_date: string;
  total_observations: number;
  overall_avg_occupancy: number;
  overall_peak_occupancy: number;
  overall_avg_utilization: number;
  data_points: HistoricalOccupancyDataPoint[];
  provenance: string;
}

export interface PeakUsageHourSummary {
  hour_of_day: number;
  avg_observed_count: number;
  peak_observed_count: number;
  avg_utilization_percentage: number;
  observation_count: number;
  is_peak: boolean;
}

export interface PeakUsageAnalysisResponse {
  zone_id?: number | null;
  days_analyzed: number;
  total_observations: number;
  peak_hour: number;
  peak_hour_avg_occupancy: number;
  lowest_hour: number;
  hourly_distribution: PeakUsageHourSummary[];
  provenance: string;
}

export interface TelemetryObservationCreate {
  zone_id: number;
  recorded_at?: string | null;
  observed_count: number;
  source_sensor_id?: string | null;
}

export interface TelemetryObservationResponse {
  id: number;
  zone_id: number;
  recorded_at: string;
  observed_count: number;
  capacity_utilization: number;
  source_sensor_id?: string | null;
  status: string;
}
