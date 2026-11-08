import { apiFetch } from './apiClient';
import type {
  LibraryFloor,
  FloorPlan,
  FloorPlanElement,
  FloorPlanDetailResponse,
  ResourceLocationResponse,
  WayfindingRouteResponse,
  SpatialCompletenessReport,
  SpatialResourceAvailability,
} from '../types/spatial';

export async function getFloors(includeInactive: boolean = false): Promise<LibraryFloor[]> {
  const query = includeInactive ? '?include_inactive=true' : '';
  return apiFetch<LibraryFloor[]>(`/api/spaces/floors${query}`);
}

export async function getFloorById(floorId: number): Promise<LibraryFloor> {
  return apiFetch<LibraryFloor>(`/api/spaces/floors/${floorId}`);
}

export async function getFloorDetail(floorId: number, asOf?: string): Promise<FloorPlanDetailResponse> {
  const query = asOf ? `?as_of=${encodeURIComponent(asOf)}` : '';
  return apiFetch<FloorPlanDetailResponse>(`/api/spaces/floors/${floorId}/detail${query}`);
}

export async function getResourceLocation(
  resourceType: string,
  resourceId: number
): Promise<ResourceLocationResponse> {
  return apiFetch<ResourceLocationResponse>(
    `/api/spaces/resources/${resourceType}/${resourceId}/location`
  );
}

export async function getWayfindingRoute(
  resourceType: string,
  resourceId: number,
  fromNodeId?: number
): Promise<WayfindingRouteResponse> {
  const query = fromNodeId ? `?from_node_id=${fromNodeId}` : '';
  return apiFetch<WayfindingRouteResponse>(
    `/api/spaces/resources/${resourceType}/${resourceId}/route${query}`
  );
}

export async function createFloor(payload: {
  floor_number: number;
  name: string;
  description?: string;
  display_order?: number;
  width?: number;
  height?: number;
}): Promise<LibraryFloor> {
  return apiFetch<LibraryFloor>('/api/spaces/floors', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateFloor(
  floorId: number,
  payload: Partial<LibraryFloor>
): Promise<LibraryFloor> {
  return apiFetch<LibraryFloor>(`/api/spaces/floors/${floorId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function getFloorLayouts(floorId: number): Promise<FloorPlan[]> {
  return apiFetch<FloorPlan[]>(`/api/spaces/floors/${floorId}/layouts`);
}

export async function createFloorLayout(
  floorId: number,
  payload: { title: string; description?: string; svg_viewbox?: string }
): Promise<FloorPlan> {
  return apiFetch<FloorPlan>(`/api/spaces/floors/${floorId}/layouts`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateLayout(
  layoutId: number,
  payload: { title?: string; description?: string; svg_viewbox?: string }
): Promise<FloorPlan> {
  return apiFetch<FloorPlan>(`/api/spaces/layouts/${layoutId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function validateLayout(
  layoutId: number
): Promise<{ is_valid: boolean; errors: string[]; warnings: string[]; mapped_resources_count?: number; elements_count?: number }> {
  return apiFetch(`/api/spaces/layouts/${layoutId}/validate`, {
    method: 'POST',
  });
}

export async function publishLayout(layoutId: number): Promise<FloorPlan> {
  return apiFetch<FloorPlan>(`/api/spaces/layouts/${layoutId}/publish`, {
    method: 'POST',
  });
}

export async function createLayoutElement(
  floorId: number,
  payload: {
    layout_id?: number;
    element_type: string;
    label?: string;
    geometry_type: string;
    geometry_data: any;
    style_properties?: any;
    display_order?: number;
  }
): Promise<FloorPlanElement> {
  return apiFetch<FloorPlanElement>(`/api/spaces/floors/${floorId}/elements`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateLayoutElement(
  elementId: number,
  payload: Partial<FloorPlanElement>
): Promise<FloorPlanElement> {
  return apiFetch<FloorPlanElement>(`/api/spaces/layout-elements/${elementId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function deleteLayoutElement(elementId: number): Promise<{ message: string }> {
  return apiFetch<{ message: string }>(`/api/spaces/layout-elements/${elementId}`, {
    method: 'DELETE',
  });
}

export async function createResourceMapping(
  floorId: number,
  payload: {
    resource_type: string;
    resource_id: number;
    label?: string;
    x: number;
    y: number;
    width?: number;
    height?: number;
    rotation?: number;
  }
): Promise<SpatialResourceAvailability> {
  return apiFetch<SpatialResourceAvailability>(`/api/spaces/floors/${floorId}/mappings`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateResourceMapping(
  mappingId: number,
  payload: {
    label?: string;
    x?: number;
    y?: number;
    width?: number;
    height?: number;
    rotation?: number;
    is_active?: boolean;
  }
): Promise<SpatialResourceAvailability> {
  return apiFetch<SpatialResourceAvailability>(`/api/spaces/mappings/${mappingId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function deleteResourceMapping(mappingId: number): Promise<{ message: string }> {
  return apiFetch<{ message: string }>(`/api/spaces/mappings/${mappingId}`, {
    method: 'DELETE',
  });
}

export async function getSpatialCompleteness(): Promise<SpatialCompletenessReport> {
  return apiFetch<SpatialCompletenessReport>('/api/spaces/spatial/completeness');
}

