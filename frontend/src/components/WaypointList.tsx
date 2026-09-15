import { GripVertical, Trash2 } from "lucide-react";
import { useState } from "react";
import type { Waypoint } from "../hooks/usePlanner";

type Props = {
  waypoints: Waypoint[];
  selectedWaypointId: string | null;
  onSelect: (id: string) => void;
  onRemove: (index: number) => void;
  onReorder: (from: number, to: number) => void;
};

export function WaypointList({
  waypoints,
  selectedWaypointId,
  onSelect,
  onRemove,
  onReorder,
}: Props) {
  const [dragIndex, setDragIndex] = useState<number | null>(null);

  if (waypoints.length === 0) {
    return null;
  }

  return (
    <section className="waypoint-list" aria-label="Route stops">
      <h2>Stops</h2>
      <ol>
        {waypoints.map((waypoint, index) => {
          const selected = waypoint.id === selectedWaypointId;
          return (
            <li
              key={waypoint.id}
              className={selected ? "selected" : ""}
              draggable
              onDragStart={() => setDragIndex(index)}
              onDragOver={(event) => event.preventDefault()}
              onDrop={() => {
                if (dragIndex !== null) {
                  onReorder(dragIndex, index);
                }
                setDragIndex(null);
              }}
              onDragEnd={() => setDragIndex(null)}
            >
              <button
                type="button"
                className="waypoint-drag-handle"
                aria-label={`Reorder ${waypoint.label}`}
                tabIndex={-1}
              >
                <GripVertical size={14} strokeWidth={1.75} />
              </button>
              <span className="waypoint-index">{index + 1}</span>
              <button
                type="button"
                className="waypoint-label"
                onClick={() => onSelect(waypoint.id)}
              >
                {waypoint.label}
              </button>
              <button
                type="button"
                className="waypoint-delete"
                onClick={() => onRemove(index)}
                aria-label={`Delete ${waypoint.label}`}
              >
                <Trash2 size={14} strokeWidth={1.75} />
              </button>
            </li>
          );
        })}
      </ol>
      <p className="hint">Drag to reorder. Click a stop to focus it on the map.</p>
    </section>
  );
}
