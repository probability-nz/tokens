// Find complete laps around successive latitude bands. A band can span two
// or more latitudes when the triangular faces alternate above and below it.
export function ringWalk(
  latitude: number[],
  neighbors: number[][],
  turn: (i: number, j: number) => number,
): number[] | undefined {
  const levels: number[][] = [];
  for (const i of latitude
    .map((_, i) => i)
    .sort((a, b) => latitude[b] - latitude[a])) {
    const last = levels[levels.length - 1];
    if (last && Math.abs(latitude[last[0]] - latitude[i]) < 1e-6) last.push(i);
    else levels.push([i]);
  }
  const bands = levels.map((_, start) => {
    const candidates: { lap: number[]; next: number }[] = [];
    const members = new Set<number>();
    for (let end = start; end < levels.length; end++) {
      for (const i of levels[end]) members.add(i);
      const first = levels[start][0];
      if (members.size === 1 && Math.abs(latitude[first]) > 1 - 1e-6) {
        candidates.push({ lap: [first], next: end + 1 });
        continue;
      }
      const adjacent = (i: number) =>
        neighbors[i].filter((j) => members.has(j));
      const edges = [...members].map(adjacent);
      if (edges.some((row) => row.length > 2)) break;
      if (edges.some((row) => row.length !== 2)) continue;
      const lap = [first];
      let current = adjacent(first)[0];
      while (current !== first) {
        const prev = lap[lap.length - 1];
        lap.push(current);
        current = adjacent(current).find((i) => i !== prev)!;
      }
      if (lap.length !== members.size) continue;
      const sweep = lap.reduce(
        (sum, i, k) => sum + turn(i, lap[(k + 1) % lap.length]),
        0,
      );
      if (Math.abs(Math.abs(sweep) - 2 * Math.PI) > 1e-5) continue;
      if (sweep < 0) lap.reverse();
      candidates.push({ lap, next: end + 1 });
    }
    return candidates;
  });
  // Changing rings must also be a one-edge roll. Rotate a lap's starting
  // point as needed to leave a valid entry into the next band.
  const failed = new Set<string>();
  function join(
    level: number,
    previous: number,
    forwardOnly: boolean,
  ): number[] | undefined {
    if (level === levels.length) return [];
    const key = level + '/' + previous;
    if (failed.has(key)) return;
    for (const { lap, next } of bands[level]) {
      const entries = lap
        .map((_, i) => i)
        .filter((i) => previous < 0 || neighbors[previous].includes(lap[i]));
      if (previous >= 0) {
        const entryCost = (i: number) => {
          const angle = turn(previous, lap[i]);
          return Math.abs(angle) + (angle < -1e-8 ? 2 * Math.PI : 0);
        };
        entries.sort((a, b) => entryCost(a) - entryCost(b));
      }
      for (const i of entries) {
        if (forwardOnly && previous >= 0 && turn(previous, lap[i]) < -1e-8)
          continue;
        const rest = join(
          next,
          lap[(i + lap.length - 1) % lap.length],
          forwardOnly,
        );
        if (rest) return [...lap.slice(i), ...lap.slice(0, i), ...rest];
      }
    }
    failed.add(key);
  }
  const forward = join(0, -1, true);
  if (forward) return forward;
  failed.clear();
  return join(0, -1, false);
}
