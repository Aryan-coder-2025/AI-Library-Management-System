import React, { useState, useRef, useCallback, useEffect } from 'react';
import type {
  FloorPlanDetailResponse,
  SpatialResourceAvailability,
  WayfindingRouteResponse,
  FloorPlanElement,
} from '../../types/spatial';

interface FloorPlanCanvasProps {
  floorDetail: FloorPlanDetailResponse;
  selectedResource: SpatialResourceAvailability | null;
  onSelectResource: (resource: SpatialResourceAvailability) => void;
  wayfindingRoute?: WayfindingRouteResponse | null;
  highlightedResourceKey?: string | null;
}

export const FloorPlanCanvas: React.FC<FloorPlanCanvasProps> = ({
  floorDetail,
  selectedResource,
  onSelectResource,
  wayfindingRoute,
  highlightedResourceKey,
}) => {
  const [zoom, setZoom] = useState<number>(1.0);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [hoveredResource, setHoveredResource] = useState<SpatialResourceAvailability | null>(null);

  const containerRef = useRef<HTMLDivElement>(null);

  // Reset zoom & pan on floor switch
  useEffect(() => {
    setZoom(1.0);
    setPan({ x: 0, y: 0 });
  }, [floorDetail.floor.id]);

  const handleZoomIn = () => setZoom((z) => Math.min(z + 0.25, 3.0));
  const handleZoomOut = () => setZoom((z) => Math.max(z - 0.25, 0.6));
  const handleResetZoom = () => {
    setZoom(1.0);
    setPan({ x: 0, y: 0 });
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button !== 0) return; // Only left click drags
    setIsDragging(true);
    setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
  };

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (!isDragging) return;
      setPan({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
    },
    [isDragging, dragStart]
  );

  const handleMouseUp = () => setIsDragging(false);

  // Wheel zoom
  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY < 0 ? 0.15 : -0.15;
    setZoom((z) => Math.min(Math.max(z + delta, 0.6), 3.0));
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'available':
        return '#22c55e'; // Green
      case 'reserved':
        return '#f59e0b'; // Amber
      case 'occupied':
        return '#ef4444'; // Red
      case 'unavailable':
      default:
        return '#94a3b8'; // Slate grey
    }
  };

  // Convert normalized 0.0-1.0 coordinates to 1000x700 viewBox canvas
  const canvasWidth = 1000;
  const canvasHeight = 700;

  const toPxX = (nx: number) => nx * canvasWidth;
  const toPxY = (ny: number) => ny * canvasHeight;

  // Render architectural elements
  const renderElement = (el: FloorPlanElement) => {
    const geo = el.geometry_data || {};
    const x = toPxX(geo.x || 0);
    const y = toPxY(geo.y || 0);
    const width = toPxX(geo.width || 0.1);
    const height = toPxY(geo.height || 0.1);
    const style = el.style_properties || {};

    if (el.element_type === 'wall') {
      return (
        <rect
          key={`elem-${el.id}`}
          x={x}
          y={y}
          width={width}
          height={height}
          fill={style.fill || '#f8fafc'}
          stroke={style.stroke || '#475569'}
          strokeWidth={style.strokeWidth || 3}
          rx={4}
        />
      );
    }

    if (el.element_type === 'zone_boundary') {
      return (
        <g key={`elem-${el.id}`}>
          <rect
            x={x}
            y={y}
            width={width}
            height={height}
            fill={style.fill || '#f0fdf4'}
            fillOpacity={0.45}
            stroke={style.stroke || '#22c55e'}
            strokeWidth={style.strokeWidth || 2}
            strokeDasharray={style.strokeDasharray || '6 4'}
            rx={8}
          />
          {el.label && (
            <text
              x={x + 12}
              y={y + 20}
              fill="#1e293b"
              fontSize="12"
              fontWeight="700"
              letterSpacing="0.02em"
            >
              {el.label.toUpperCase()}
            </text>
          )}
        </g>
      );
    }

    if (el.element_type === 'stairs' || el.element_type === 'elevator') {
      return (
        <g key={`elem-${el.id}`}>
          <rect
            x={x}
            y={y}
            width={width}
            height={height}
            fill={style.fill || '#e2e8f0'}
            stroke={style.stroke || '#64748b'}
            strokeWidth={1.5}
            rx={4}
          />
          <text
            x={x + width / 2}
            y={y + height / 2 - 4}
            fill="#475569"
            fontSize="18"
            textAnchor="middle"
          >
            🏢
          </text>
          <text
            x={x + width / 2}
            y={y + height / 2 + 16}
            fill="#334155"
            fontSize="10"
            fontWeight="600"
            textAnchor="middle"
          >
            {el.label || 'Stairs / Lift'}
          </text>
        </g>
      );
    }

    if (el.element_type === 'restroom') {
      return (
        <g key={`elem-${el.id}`}>
          <rect
            x={x}
            y={y}
            width={width}
            height={height}
            fill={style.fill || '#f1f5f9'}
            stroke={style.stroke || '#94a3b8'}
            strokeWidth={1.5}
            rx={4}
          />
          <text
            x={x + width / 2}
            y={y + height / 2 - 2}
            fill="#475569"
            fontSize="18"
            textAnchor="middle"
          >
            🚻
          </text>
          <text
            x={x + width / 2}
            y={y + height / 2 + 16}
            fill="#475569"
            fontSize="10"
            fontWeight="600"
            textAnchor="middle"
          >
            Restrooms
          </text>
        </g>
      );
    }

    if (el.element_type === 'service_desk') {
      return (
        <g key={`elem-${el.id}`}>
          <rect
            x={x}
            y={y}
            width={width}
            height={height}
            fill={style.fill || '#e0e7ff'}
            stroke={style.stroke || '#4f46e5'}
            strokeWidth={2}
            rx={6}
          />
          <text
            x={x + width / 2}
            y={y + height / 2 + 4}
            fill="#3730a3"
            fontSize="12"
            fontWeight="700"
            textAnchor="middle"
          >
            ℹ️ {el.label || 'Service Desk'}
          </text>
        </g>
      );
    }

    if (el.element_type === 'entrance') {
      return (
        <g key={`elem-${el.id}`}>
          <rect
            x={x}
            y={y}
            width={width}
            height={height}
            fill="#22c55e"
            stroke="#15803d"
            strokeWidth={2}
            rx={3}
          />
          <text
            x={x + width / 2}
            y={y - 8}
            fill="#15803d"
            fontSize="11"
            fontWeight="700"
            textAnchor="middle"
          >
            ▲ MAIN ENTRANCE
          </text>
        </g>
      );
    }

    if (el.element_type === 'facility') {
      return (
        <g key={`elem-${el.id}`}>
          <rect
            x={x}
            y={y}
            width={width}
            height={height}
            fill={style.fill || '#fef3c7'}
            stroke={style.stroke || '#d97706'}
            strokeWidth={1.5}
            rx={6}
          />
          <text
            x={x + width / 2}
            y={y + height / 2 + 4}
            fill="#92400e"
            fontSize="12"
            fontWeight="700"
            textAnchor="middle"
          >
            ☕ {el.label}
          </text>
        </g>
      );
    }

    return null;
  };

  // Filter resources: rooms vs seats
  const roomResources = floorDetail.resources.filter((r) => r.resource_type === 'room');
  const seatResources = floorDetail.resources.filter((r) => r.resource_type === 'seat');

  return (
    <div
      ref={containerRef}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onWheel={handleWheel}
      style={{
        position: 'relative',
        width: '100%',
        height: '620px',
        backgroundColor: '#0f172a',
        borderRadius: '12px',
        overflow: 'hidden',
        userSelect: 'none',
        cursor: isDragging ? 'grabbing' : 'grab',
        boxShadow: 'inset 0 2px 8px rgba(0,0,0,0.4)',
        border: '1px solid #334155',
      }}
    >
      {/* Zoom / Pan Controls Overlay */}
      <div
        style={{
          position: 'absolute',
          top: 16,
          right: 16,
          zIndex: 20,
          display: 'flex',
          flexDirection: 'column',
          gap: '6px',
          background: 'rgba(30, 41, 59, 0.85)',
          backdropFilter: 'blur(8px)',
          padding: '6px',
          borderRadius: '8px',
          border: '1px solid #475569',
        }}
      >
        <button
          type="button"
          onClick={handleZoomIn}
          title="Zoom In"
          style={{
            width: '32px',
            height: '32px',
            background: '#334155',
            color: '#f8fafc',
            border: 'none',
            borderRadius: '6px',
            fontWeight: 'bold',
            fontSize: '16px',
            cursor: 'pointer',
          }}
        >
          +
        </button>
        <button
          type="button"
          onClick={handleZoomOut}
          title="Zoom Out"
          style={{
            width: '32px',
            height: '32px',
            background: '#334155',
            color: '#f8fafc',
            border: 'none',
            borderRadius: '6px',
            fontWeight: 'bold',
            fontSize: '16px',
            cursor: 'pointer',
          }}
        >
          −
        </button>
        <button
          type="button"
          onClick={handleResetZoom}
          title="Reset View"
          style={{
            width: '32px',
            height: '32px',
            background: '#334155',
            color: '#94a3b8',
            border: 'none',
            borderRadius: '6px',
            fontSize: '11px',
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          ↺
        </button>
      </div>

      {/* Hover Tooltip Overlay */}
      {hoveredResource && (
        <div
          style={{
            position: 'absolute',
            bottom: 16,
            left: 16,
            zIndex: 20,
            background: 'rgba(15, 23, 42, 0.9)',
            backdropFilter: 'blur(8px)',
            color: '#f8fafc',
            padding: '8px 14px',
            borderRadius: '8px',
            border: `1px solid ${getStatusColor(hoveredResource.availability_status)}`,
            fontSize: '0.85rem',
            pointerEvents: 'none',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
          }}
        >
          <span
            style={{
              width: '10px',
              height: '10px',
              borderRadius: '50%',
              backgroundColor: getStatusColor(hoveredResource.availability_status),
              display: 'inline-block',
            }}
          />
          <div>
            <strong>{hoveredResource.label || `${hoveredResource.resource_type.toUpperCase()} #${hoveredResource.resource_id}`}</strong>
            <span style={{ color: '#94a3b8', marginLeft: '6px' }}>
              ({hoveredResource.availability_status.toUpperCase()})
            </span>
            {hoveredResource.capacity && (
              <span style={{ color: '#cbd5e1', marginLeft: '8px' }}>
                Cap: {hoveredResource.capacity}
              </span>
            )}
          </div>
        </div>
      )}

      {/* SVG Canvas */}
      <svg
        viewBox="0 0 1000 700"
        style={{
          width: '100%',
          height: '100%',
          transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
          transformOrigin: 'center center',
          transition: isDragging ? 'none' : 'transform 0.15s ease-out',
        }}
      >
        {/* Architectural elements layer */}
        <g id="structural-elements">
          {floorDetail.elements.map((el) => renderElement(el))}
        </g>

        {/* Study Rooms Layer */}
        <g id="study-rooms">
          {roomResources.map((rm) => {
            const rx = toPxX(rm.x - (rm.width || 0.12) / 2);
            const ry = toPxY(rm.y - (rm.height || 0.12) / 2);
            const rw = toPxX(rm.width || 0.12);
            const rh = toPxY(rm.height || 0.12);
            const statusColor = getStatusColor(rm.availability_status);
            const isSelected =
              selectedResource?.resource_type === 'room' &&
              selectedResource?.resource_id === rm.resource_id;

            return (
              <g
                key={`room-${rm.resource_id}`}
                onClick={(e) => {
                  e.stopPropagation();
                  onSelectResource(rm);
                }}
                onMouseEnter={() => setHoveredResource(rm)}
                onMouseLeave={() => setHoveredResource(null)}
                style={{ cursor: 'pointer' }}
                tabIndex={0}
                role="button"
                aria-label={`Study Room ${rm.label}, status ${rm.availability_status}`}
              >
                {/* Room footprint */}
                <rect
                  x={rx}
                  y={ry}
                  width={rw}
                  height={rh}
                  fill={isSelected ? '#312e81' : '#1e293b'}
                  stroke={isSelected ? '#818cf8' : statusColor}
                  strokeWidth={isSelected ? 3 : 2}
                  rx={8}
                />
                {/* Status indicator bar on room top */}
                <rect
                  x={rx}
                  y={ry}
                  width={rw}
                  height={5}
                  fill={statusColor}
                  rx={2}
                />
                {/* Room Label */}
                <text
                  x={rx + rw / 2}
                  y={ry + 24}
                  fill="#f8fafc"
                  fontSize="12"
                  fontWeight="700"
                  textAnchor="middle"
                >
                  {rm.details?.room_code || rm.label}
                </text>
                <text
                  x={rx + rw / 2}
                  y={ry + 42}
                  fill="#94a3b8"
                  fontSize="10"
                  textAnchor="middle"
                >
                  {rm.label}
                </text>
                {/* Capacity badge */}
                <text
                  x={rx + rw / 2}
                  y={ry + rh - 12}
                  fill="#cbd5e1"
                  fontSize="10"
                  fontWeight="600"
                  textAnchor="middle"
                >
                  👥 {rm.capacity || 6} seats
                </text>
              </g>
            );
          })}
        </g>

        {/* Study Seats Layer */}
        <g id="study-seats">
          {seatResources.map((seat) => {
            const sx = toPxX(seat.x);
            const sy = toPxY(seat.y);
            const statusColor = getStatusColor(seat.availability_status);
            const isSelected =
              selectedResource?.resource_type === 'seat' &&
              selectedResource?.resource_id === seat.resource_id;
            const isHighlighted =
              highlightedResourceKey === `seat_${seat.resource_id}`;

            return (
              <g
                key={`seat-${seat.resource_id}`}
                onClick={(e) => {
                  e.stopPropagation();
                  onSelectResource(seat);
                }}
                onMouseEnter={() => setHoveredResource(seat)}
                onMouseLeave={() => setHoveredResource(null)}
                style={{ cursor: 'pointer' }}
                tabIndex={0}
                role="button"
                aria-label={`Study Seat ${seat.label}, status ${seat.availability_status}`}
              >
                {/* Outer halo when selected or highlighted */}
                {(isSelected || isHighlighted) && (
                  <circle
                    cx={sx}
                    cy={sy}
                    r={18}
                    fill="none"
                    stroke="#38bdf8"
                    strokeWidth={3}
                    strokeDasharray="4 2"
                    opacity={0.9}
                  />
                )}
                {/* Seat circle marker */}
                <circle
                  cx={sx}
                  cy={sy}
                  r={12}
                  fill={statusColor}
                  stroke={isSelected ? '#ffffff' : '#0f172a'}
                  strokeWidth={2}
                />
                {/* Seat number inside */}
                <text
                  x={sx}
                  y={sy + 3.5}
                  fill="#ffffff"
                  fontSize="8"
                  fontWeight="bold"
                  textAnchor="middle"
                  pointerEvents="none"
                >
                  {(seat.label || '').replace(/.*-/, '')}
                </text>
              </g>
            );
          })}
        </g>

        {/* Wayfinding Route Polyline Layer */}
        {wayfindingRoute && wayfindingRoute.path_points.length > 1 && (
          <g id="wayfinding-route">
            <polyline
              points={wayfindingRoute.path_points
                .map((pt) => `${toPxX(pt[0])},${toPxY(pt[1])}`)
                .join(' ')}
              fill="none"
              stroke="#38bdf8"
              strokeWidth={4}
              strokeDasharray="8 6"
              strokeLinecap="round"
              strokeLinejoin="round"
              style={{
                filter: 'drop-shadow(0 0 6px #0284c7)',
              }}
            />
            {/* Start Node Indicator */}
            {wayfindingRoute.path_points[0] && (
              <circle
                cx={toPxX(wayfindingRoute.path_points[0][0])}
                cy={toPxY(wayfindingRoute.path_points[0][1])}
                r={8}
                fill="#22c55e"
                stroke="#ffffff"
                strokeWidth={2}
              />
            )}
            {/* Destination Target Pulsing Beacon */}
            {wayfindingRoute.path_points[wayfindingRoute.path_points.length - 1] && (
              <g>
                <circle
                  cx={toPxX(wayfindingRoute.path_points[wayfindingRoute.path_points.length - 1][0])}
                  cy={toPxY(wayfindingRoute.path_points[wayfindingRoute.path_points.length - 1][1])}
                  r={16}
                  fill="none"
                  stroke="#ef4444"
                  strokeWidth={2.5}
                />
                <circle
                  cx={toPxX(wayfindingRoute.path_points[wayfindingRoute.path_points.length - 1][0])}
                  cy={toPxY(wayfindingRoute.path_points[wayfindingRoute.path_points.length - 1][1])}
                  r={7}
                  fill="#ef4444"
                />
              </g>
            )}
          </g>
        )}
      </svg>
    </div>
  );
};

