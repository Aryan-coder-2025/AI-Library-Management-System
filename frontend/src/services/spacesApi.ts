import { apiFetch } from './apiClient';
import type {
  StudyZone,
  StudySpaceReservation,
  StudySpaceReservationCreate,
  ReservationPaginationResponse,
  SpaceAvailabilityResponse,
  ReservationQRResponse,
  ReservationSweepReport,
  CurrentOccupancyResponse,
  ZoneOccupancySummary,
  ResourceOccupancyResponse,
  HistoricalOccupancyResponse,
  PeakUsageAnalysisResponse,
  TelemetryObservationCreate,
  TelemetryObservationResponse,
} from '../types/library';

export async function getMyReservations(
  statusFilter?: string,
  page: number = 1,
  pageSize: number = 10
): Promise<ReservationPaginationResponse> {
  const params = new URLSearchParams();
  if (statusFilter && statusFilter !== 'all') {
    params.set('status_filter', statusFilter);
  }
  params.set('page', String(page));
  params.set('page_size', String(pageSize));

  const url = `/api/spaces/reservations/me?${params.toString()}`;
  return apiFetch<ReservationPaginationResponse>(url);
}

export async function getAllReservations(
  statusFilter?: string,
  resourceType?: string,
  page: number = 1,
  pageSize: number = 20
): Promise<ReservationPaginationResponse> {
  const params = new URLSearchParams();
  if (statusFilter && statusFilter !== 'all') {
    params.set('status_filter', statusFilter);
  }
  if (resourceType && resourceType !== 'all') {
    params.set('resource_type', resourceType);
  }
  params.set('page', String(page));
  params.set('page_size', String(pageSize));

  const url = `/api/spaces/reservations/all?${params.toString()}`;
  return apiFetch<ReservationPaginationResponse>(url);
}

export async function getReservationQR(reservationId: number): Promise<ReservationQRResponse> {
  return apiFetch<ReservationQRResponse>(`/api/spaces/reservations/${reservationId}/qr`);
}

export async function checkInReservation(
  reservationId: number,
  actualAttendees?: number | null
): Promise<StudySpaceReservation> {
  return apiFetch<StudySpaceReservation>(`/api/spaces/reservations/${reservationId}/check-in`, {
    method: 'POST',
    body: JSON.stringify({ actual_attendees: actualAttendees }),
  });
}

export async function checkInByToken(
  token: string,
  actualAttendees?: number | null
): Promise<StudySpaceReservation> {
  return apiFetch<StudySpaceReservation>('/api/spaces/reservations/check-in-by-token', {
    method: 'POST',
    body: JSON.stringify({ token, actual_attendees: actualAttendees }),
  });
}

export async function cancelReservation(reservationId: number): Promise<StudySpaceReservation> {
  return apiFetch<StudySpaceReservation>(`/api/spaces/reservations/${reservationId}/cancel`, {
    method: 'POST',
  });
}

export async function querySpaceAvailability(
  startTime: string,
  endTime: string,
  resourceType?: string,
  zoneId?: number
): Promise<SpaceAvailabilityResponse> {
  const params = new URLSearchParams({
    start_time: startTime,
    end_time: endTime,
  });
  if (resourceType && resourceType !== 'all') {
    params.set('resource_type', resourceType);
  }
  if (zoneId) {
    params.set('zone_id', String(zoneId));
  }

  return apiFetch<SpaceAvailabilityResponse>(`/api/spaces/availability?${params.toString()}`);
}

export async function getStudyZones(): Promise<StudyZone[]> {
  return apiFetch<StudyZone[]>('/api/spaces/zones');
}

export async function createReservation(
  payload: StudySpaceReservationCreate
): Promise<StudySpaceReservation> {
  return apiFetch<StudySpaceReservation>('/api/spaces/reservations', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function sweepReservations(): Promise<ReservationSweepReport> {
  return apiFetch<ReservationSweepReport>('/api/spaces/reservations/sweep', {
    method: 'POST',
  });
}

// ── Stage 10.4 Occupancy & Telemetry Services ────────────────────────────────

export async function getCurrentOccupancy(): Promise<CurrentOccupancyResponse> {
  return apiFetch<CurrentOccupancyResponse>('/api/spaces/occupancy/current');
}

export async function getZoneOccupancy(): Promise<ZoneOccupancySummary[]> {
  return apiFetch<ZoneOccupancySummary[]>('/api/spaces/occupancy/zones');
}

export async function getResourceOccupancy(): Promise<ResourceOccupancyResponse> {
  return apiFetch<ResourceOccupancyResponse>('/api/spaces/occupancy/resources');
}

export async function getHistoricalOccupancy(params?: {
  startDate?: string;
  endDate?: string;
  daysBack?: number;
  zoneId?: number;
  interval?: 'day' | 'hour';
}): Promise<HistoricalOccupancyResponse> {
  const q = new URLSearchParams();
  if (params?.startDate) q.set('start_date', params.startDate);
  if (params?.endDate) q.set('end_date', params.endDate);
  if (params?.daysBack) q.set('days_back', String(params.daysBack));
  if (params?.zoneId) q.set('zone_id', String(params.zoneId));
  if (params?.interval) q.set('interval', params.interval);
  const queryStr = q.toString() ? `?${q.toString()}` : '';
  return apiFetch<HistoricalOccupancyResponse>(`/api/spaces/occupancy/historical${queryStr}`);
}

export async function getPeakUsageHours(params?: {
  zoneId?: number;
  daysBack?: number;
}): Promise<PeakUsageAnalysisResponse> {
  const q = new URLSearchParams();
  if (params?.zoneId) q.set('zone_id', String(params.zoneId));
  if (params?.daysBack) q.set('days_back', String(params.daysBack));
  const queryStr = q.toString() ? `?${q.toString()}` : '';
  return apiFetch<PeakUsageAnalysisResponse>(`/api/spaces/occupancy/peak-hours${queryStr}`);
}

export async function ingestTelemetryObservation(
  payload: TelemetryObservationCreate
): Promise<TelemetryObservationResponse> {
  return apiFetch<TelemetryObservationResponse>('/api/spaces/occupancy/telemetry', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}


