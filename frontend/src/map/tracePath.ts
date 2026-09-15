export type ParsedRoadId = {
  source: number;
  target: number;
  key: number;
};

export type TraceClickAction = "undo-last" | "noop" | "extend";

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

function matchesVisual(selectedId: string, candidates: string[]): boolean {
  const reversed = reverseRoadId(selectedId);
  return candidates.includes(selectedId) || (reversed !== null && candidates.includes(reversed));
}

export function detectTraceClick(selected: string[], clickedIds: string[]): TraceClickAction {
  if (selected.length === 0) {
    return "extend";
  }
  const candidates = uniqueOrientations(clickedIds);
  if (candidates.length === 0) {
    return "extend";
  }
  const last = selected[selected.length - 1];
  if (matchesVisual(last, candidates)) {
    return "undo-last";
  }
  if (selected.some((roadId) => matchesVisual(roadId, candidates))) {
    return "noop";
  }
  return "extend";
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
