import random

import numpy as np

from bot.memory.projection import project_2d


def _svd_projection(centroids: dict[str, list[float]]) -> np.ndarray:
    X = np.array(list(centroids.values()))
    X -= X.mean(axis=0)
    U, S, _ = np.linalg.svd(X, full_matrices=False)
    proj = U[:, :2] * S[:2]
    for col in range(2):
        lo, hi = proj[:, col].min(), proj[:, col].max()
        proj[:, col] = 2 * (proj[:, col] - lo) / (hi - lo) - 1
    return proj


def test_projection_matches_svd_up_to_axis_sign():
    rng = random.Random(7)
    # Two dominant directions over noise, like clustered embedding centroids.
    a = [rng.gauss(0, 1) for _ in range(64)]
    b = [rng.gauss(0, 1) for _ in range(64)]
    centroids = {
        f"user:{i}": [
            3 * s * x + 1.5 * t * y + rng.gauss(0, 0.05) for x, y in zip(a, b)
        ]
        for i in range(40)
        for s, t in [(rng.gauss(0, 1), rng.gauss(0, 1))]
    }

    ours = np.array(list(project_2d(centroids).values()))
    expected = _svd_projection(centroids)

    for col in range(2):
        same = np.abs(ours[:, col] - expected[:, col]).max()
        mirrored = np.abs(ours[:, col] + expected[:, col]).max()
        assert min(same, mirrored) < 1e-6


def test_projection_is_deterministic_and_bounded():
    rng = random.Random(1)
    centroids = {str(i): [rng.random() for _ in range(16)] for i in range(12)}

    first = project_2d(centroids)

    assert first == project_2d(centroids)
    assert list(first) == list(centroids)
    for axis in range(2):
        values = [point[axis] for point in first.values()]
        assert min(values) == -1.0
        assert max(values) == 1.0


def test_fewer_than_two_centroids_sit_at_the_origin():
    assert project_2d({}) == {}
    assert project_2d({"only": [0.2, 0.9]}) == {"only": (0.0, 0.0)}


def test_identical_centroids_do_not_divide_by_zero():
    coords = project_2d({"a": [1.0, 2.0], "b": [1.0, 2.0], "c": [1.0, 2.0]})

    assert set(coords) == {"a", "b", "c"}
    assert all(abs(x) <= 1 and abs(y) <= 1 for x, y in coords.values())
