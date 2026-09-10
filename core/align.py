from functools import lru_cache

import panphon.distance

_dst = panphon.distance.Distance()

MAX_WEIGHTED_DISTANCE = 7.0
INS_COST = 1.0
DEL_COST = 1.0

UNKNOWN_PHONES: set[str] = set()


@lru_cache(maxsize=100_000)
def sub_cost(a: str, b: str) -> float:
    if a == b:
        return 0.0
    try:
        d = _dst.weighted_feature_edit_distance(a, b)
    except Exception:
        UNKNOWN_PHONES.update([a, b])
        return 1.0
    if d is None:
        UNKNOWN_PHONES.update([a, b])
        return 1.0
    return min(float(d) / MAX_WEIGHTED_DISTANCE, 1.0)


def align(ref: list[str], hyp: list[str]) -> tuple[float, list[tuple]]:
    n, m = len(ref), len(hyp)

    dist = [[0.0] * (m + 1) for _ in range(n + 1)]
    back: list[list[tuple | None]] = [[None] * (m + 1) for _ in range(n + 1)]

    for i in range(1, n + 1):
        dist[i][0] = dist[i - 1][0] + DEL_COST
        back[i][0] = ("del", i - 1)
    for j in range(1, m + 1):
        dist[0][j] = dist[0][j - 1] + INS_COST
        back[0][j] = ("ins", None)

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            c = sub_cost(ref[i - 1], hyp[j - 1])
            candidates = [
                (dist[i - 1][j - 1] + c, ("sub", i - 1)),
                (dist[i - 1][j] + DEL_COST, ("del", i - 1)),
                (dist[i][j - 1] + INS_COST, ("ins", None)),
            ]
            dist[i][j], back[i][j] = min(candidates, key=lambda x: x[0])

    ops: list[tuple] = []
    i, j = n, m
    while i > 0 or j > 0:
        kind, ri = back[i][j]
        if kind == "sub":
            c = sub_cost(ref[i - 1], hyp[j - 1])
            label = "ok" if c == 0.0 else "sub"
            ops.append((label, ri, ref[i - 1], hyp[j - 1], c))
            i, j = i - 1, j - 1
        elif kind == "del":
            ops.append(("del", ri, ref[i - 1], None, DEL_COST))
            i -= 1
        else:
            ops.append(("ins", None, None, hyp[j - 1], INS_COST))
            j -= 1

    ops.reverse()
    return dist[n][m], ops


def describe(ops: list[tuple]) -> str:
    parts = []
    for kind, _ri, rp, hp, _c in ops:
        if kind == "ok":
            parts.append(rp)
        elif kind == "sub":
            parts.append(f"[{rp}->{hp}]")
        elif kind == "del":
            parts.append(f"[{rp}->_]")
        else:
            parts.append(f"[_->{hp}]")
    return " ".join(parts)
