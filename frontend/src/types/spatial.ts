export interface LibraryFloor {
  id: number;
  floor_number: number;
  name: string;
  description?: string | null;
  display_order: number;
  width: number;
  height: number;
  is_active: boolean;
  published_layout_id?: number | null;
  created_at: string;
  updated_at: string;
}

export interface FloorPlanElement {
  id: number;
  floor_id: number;
  layout_id?: number | null;
  element_type: string; // wall, door, entrance, exit, stairs, elevator, restroom, service_desk, label, facility, zone_boundary, room
  label?: string | null;
  geometry_type: string; // rect, circle, polygon, path, text
  geometry_data: {
    x?: number;
    y?: number;
    width?: number;
    height?: number;
    radius?: number;
    points?: number[][];
    text?: string;
  };
  style_properties?: {
    fill?: string;
    stroke?: string;
    strokeWidth?: number;
    strokeDasharray?: string;
    opacity?: number;
    fontSize?: number;
  } | null;
  display_order: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface FloorPlan {
  id: number;
  floor_id: number;
  version: number;
  status: 'draft' | 'published' | 'archived';
  title: string;
  description?: string | null;
  svg_viewbox: string;
  created_by_user_id?: number | null;
  published_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface SpatialResourceAvailability {
  resource_type: 'seat' | 'room' | 'zone';
  resource_id: number;
  label?: string | null;
  availability_status: 'available' | 'reserved' | 'occupied' | 'unavailable' | 'unknown';
  current_attendees?: number | null;
  capacity?: number | null;
  provenance: string;
  x: number;
  y: number;
  width?: number | null;
  height?: number | null;
  rotation: number;
  zone_id?: number | null;
  zone_code?: string | null;
  zone_name?: string | null;
  details?: {
    seat_code?: string;
    has_power_outlet?: boolean;
    has_monitor?: boolean;
    is_accessible?: boolean;
    room_code?: string;
    capacity?: number;
    display_type?: string;
    has_whiteboard?: boolean;
    noise_policy?: string;
    total_capacity?: number;
  } | null;
}

export interface FloorPlanDetailResponse {
  floor: LibraryFloor;
  layout?: FloorPlan | null;
  elements: FloorPlanElement[];
  resources: SpatialResourceAvailability[];
  is_demonstration_layout: boolean;
  disclosure: string;
}

export interface ResourceLocationResponse {
  resource_type: string;
  resource_id: number;
  label?: string | null;
  floor_id: number;
  floor_number: number;
  floor_name: string;
  zone_id?: number | null;
  zone_code?: string | null;
  zone_name?: string | null;
  x: number;
  y: number;
  availability_status: string;
  directional_guidance?: string | null;
  is_demonstration: boolean;
  disclosure: string;
}

export interface WayfindingStep {
  step_number: number;
  instruction: string;
  floor_number: number;
  node_type: string;
  x: number;
  y: number;
}

export interface WayfindingRouteResponse {
  destination_resource_type: string;
  destination_resource_id: number;
  destination_label: string;
  destination_floor_number: number;
  total_distance: number;
  is_accessible: boolean;
  path_points: number[][];
  steps: WayfindingStep[];
  is_demonstration: boolean;
  disclosure: string;
}

export interface SpatialCompletenessReport {
  total_zones: number;
  mapped_zones: number;
  unmapped_zone_ids: number[];
  total_seats: number;
  mapped_seats: number;
  unmapped_seat_ids: number[];
  total_rooms: number;
  mapped_rooms: number;
  unmapped_room_ids: number[];
  mapping_completeness_percentage: number;
  published_floors_count: number;
  draft_floors_count: number;
}

