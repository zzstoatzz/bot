"""Two-dimensional layout for the memory graph."""

from math import sqrt, sumprod

_ITERATIONS = 500
_TOLERANCE = 1e-12


def _top_eigenvector(
    gram: list[list[float]], orthogonal_to: list[list[float]], phase: float
) -> list[float]:
    """Power iteration from a fixed start, so the same input gives the same layout."""
    n = len(gram)
    # Centred data puts the all-ones vector in the null space, so the start must vary.
    v = [((i + 1) * 0.6180339887 + phase) % 1.0 - 0.5 for i in range(n)]
    for _ in range(_ITERATIONS):
        w = [sumprod(row, v) for row in gram]
        for u in orthogonal_to:
            overlap = sumprod(w, u)
            w = [a - overlap * b for a, b in zip(w, u)]
        norm = sqrt(sumprod(w, w))
        if norm < _TOLERANCE:
            return [0.0] * n
        w = [a / norm for a in w]
        moved = max(abs(a - b) for a, b in zip(w, v))
        v = w
        if moved < _TOLERANCE:
            break
    return v


def project_2d(centroids: dict[str, list[float]]) -> dict[str, tuple[float, float]]:
    """Place each centroid on its top two principal components, scaled to [-1, 1].

    The eigenvectors of the Gram matrix of the centred rows are the left
    singular vectors an SVD would return, and the per-axis rescaling makes the
    singular values irrelevant.
    """
    if len(centroids) < 2:
        return {nid: (0.0, 0.0) for nid in centroids}

    ids = list(centroids)
    rows = [centroids[nid] for nid in ids]
    n = len(rows)
    means = [sum(column) / n for column in zip(*rows)]
    centred = [[a - m for a, m in zip(row, means)] for row in rows]

    gram = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i, n):
            gram[i][j] = gram[j][i] = sumprod(centred[i], centred[j])

    first = _top_eigenvector(gram, [], 0.0)
    second = _top_eigenvector(gram, [first], 0.5)

    axes = []
    for axis in (first, second):
        lo, hi = min(axis), max(axis)
        span = hi - lo or 1.0
        axes.append([2 * (a - lo) / span - 1 for a in axis])
    return {nid: (axes[0][i], axes[1][i]) for i, nid in enumerate(ids)}
