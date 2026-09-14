export type ParsedRoadId = {
  source: number;
  target: number;
  key: number;
};

export type TraceStep = {
  roadIds: string[];
  side: "append" | "prepend";
};

export type TraceClickAction = "undo-last" | "undo-first" | "noop" | "extend";

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

function idsMatch(left: string, right: string): boolean {
  return left === right || reverseRoadId(left) === right;
}

export function flattenTraceSteps(steps: TraceStep[]): string[] {
  let result: string[] = [];
  for (const step of steps) {
    result = step.side === "prepend" ? [...step.roadIds, ...result] : [...result, ...step.roadIds];
  }
  return result;
}

export function detectTraceClick(steps: TraceStep[], clickedIds: string[]): TraceClickAction {
  const selected = flattenTraceSteps(steps);
  if (selected.length === 0) {
    return "extend";
  }
  const candidates = uniqueOrientations(clickedIds);
  if (candidates.length === 0) {
    return "extend";
  }
  const first = selected[0];
  const last = selected[selected.length - 1];
  const hitsFirst = matchesVisual(first, candidates);
  const hitsLast = matchesVisual(last, candidates);
  if (hitsLast) {
    return "undo-last";
  }
  if (hitsFirst) {
    return "undo-first";
  }
  if (selected.some((roadId) => matchesVisual(roadId, candidates))) {
    return "noop";
  }
  return "extend";
}

export function applyTraceExtension(steps: TraceStep[], nextRoadIds: string[]): TraceStep[] {
  const previous = flattenTraceSteps(steps);
  if (previous.length === 0) {
    return [{ roadIds: nextRoadIds, side: "append" }];
  }

  const step = stepFromExtension(previous, nextRoadIds);
  const trial = [...steps, step];
  const flattened = flattenTraceSteps(trial);
  if (
    flattened.length === nextRoadIds.length &&
    flattened.every((roadId, index) => idsMatch(roadId, nextRoadIds[index]))
  ) {
    return trial;
  }
  return [{ roadIds: nextRoadIds, side: "append" }];
}

function stepFromExtension(previous: string[], next: string[]): TraceStep {
  if (next.length >= previous.length) {
    const appendPrefix = next.slice(0, previous.length);
    if (appendPrefix.every((roadId, index) => idsMatch(roadId, previous[index]))) {
      return { roadIds: next.slice(previous.length), side: "append" };
    }
    const prependSuffix = next.slice(next.length - previous.length);
    if (prependSuffix.every((roadId, index) => idsMatch(roadId, previous[index]))) {
      return { roadIds: next.slice(0, next.length - previous.length), side: "prepend" };
    }
  }
  return { roadIds: next, side: "append" };
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
