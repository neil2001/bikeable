export type TraceClickResult =
  | { type: "select"; roadIds: string[] }
  | { type: "undo"; roadIds: string[] }
  | { type: "error"; message: string };

export type ParsedRoadId = {
  source: number;
  target: number;
  key: number;
};

const DISCONNECTED_HINT = "Pick a road that connects to your path.";

export function parseRoadId(roadId: string): ParsedRoadId | null {
  const parts = roadId.split(":");
  if (parts.length !== 3) {
    return null;
  }
  const source = Number(parts[0]);
  const target = Number(parts[1]);
  const key = Number(parts[2]);
  if (![source, target, key].every(Number.isFinite)) {
    return null;
  }
  return { source, target, key };
}

export function reverseRoadId(roadId: string): string | null {
  const parsed = parseRoadId(roadId);
  if (parsed === null) {
    return null;
  }
  return `${parsed.target}:${parsed.source}:${parsed.key}`;
}

function uniqueOrientations(roadIds: string[]): string[] {
  const seen = new Set<string>();
  const ordered: string[] = [];
  for (const roadId of roadIds) {
    if (!parseRoadId(roadId)) {
      continue;
    }
    if (!seen.has(roadId)) {
      seen.add(roadId);
      ordered.push(roadId);
    }
    const reversed = reverseRoadId(roadId);
    if (reversed && !seen.has(reversed)) {
      seen.add(reversed);
      ordered.push(reversed);
    }
  }
  return ordered;
}

function walkEnds(roadIds: string[]): { tail: number; head: number } | null {
  if (roadIds.length === 0) {
    return null;
  }
  const first = parseRoadId(roadIds[0]);
  const last = parseRoadId(roadIds[roadIds.length - 1]);
  if (!first || !last) {
    return null;
  }
  return { tail: first.source, head: last.target };
}

function matchesVisual(selectedId: string, candidates: string[]): boolean {
  const reversed = reverseRoadId(selectedId);
  return candidates.includes(selectedId) || (reversed !== null && candidates.includes(reversed));
}

export function applyTraceClick(
  selected: string[],
  clickedIds: string[],
): TraceClickResult {
  const candidates = uniqueOrientations(clickedIds);
  if (candidates.length === 0) {
    return { type: "error", message: DISCONNECTED_HINT };
  }

  if (selected.length === 0) {
    return { type: "select", roadIds: [clickedIds[0]] };
  }

  const first = selected[0];
  const last = selected[selected.length - 1];
  const hitsFirst = matchesVisual(first, candidates);
  const hitsLast = matchesVisual(last, candidates);

  if (hitsFirst || hitsLast) {
    if (selected.length === 1) {
      return { type: "undo", roadIds: [] };
    }
    if (hitsLast && !hitsFirst) {
      return { type: "undo", roadIds: selected.slice(0, -1) };
    }
    if (hitsFirst && !hitsLast) {
      return { type: "undo", roadIds: selected.slice(1) };
    }
    return { type: "undo", roadIds: selected.slice(0, -1) };
  }

  const ends = walkEnds(selected);
  if (!ends) {
    return { type: "error", message: DISCONNECTED_HINT };
  }

  for (const candidate of candidates) {
    const parsed = parseRoadId(candidate);
    if (!parsed) {
      continue;
    }
    if (parsed.source === ends.head) {
      return { type: "select", roadIds: [...selected, candidate] };
    }
    if (parsed.target === ends.tail) {
      return { type: "select", roadIds: [candidate, ...selected] };
    }
  }

  if (selected.length === 1) {
    const flipped = reverseRoadId(selected[0]);
    if (flipped) {
      const flippedEnds = walkEnds([flipped]);
      if (flippedEnds) {
        for (const candidate of candidates) {
          const parsed = parseRoadId(candidate);
          if (!parsed) {
            continue;
          }
          if (parsed.source === flippedEnds.head) {
            return { type: "select", roadIds: [flipped, candidate] };
          }
          if (parsed.target === flippedEnds.tail) {
            return { type: "select", roadIds: [candidate, flipped] };
          }
        }
      }
    }
  }

  return { type: "error", message: DISCONNECTED_HINT };
}

export function highlightRoadIds(selected: string[]): string[] {
  const ids = new Set<string>();
  for (const roadId of selected) {
    ids.add(roadId);
    const reversed = reverseRoadId(roadId);
    if (reversed) {
      ids.add(reversed);
    }
  }
  return [...ids];
}
