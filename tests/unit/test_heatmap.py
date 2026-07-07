import numpy as np

from vision.heatmap import HeatmapAccumulator


def test_accumulates_and_normalizes():
    hm = HeatmapAccumulator(grid_w=10, grid_h=10)
    hm.add_point(0.5, 0.5)
    hm.add_point(0.5, 0.5)
    hm.add_point(0.1, 0.1)
    norm = hm.normalized()
    assert norm.max() == 1.0
    assert norm[5, 5] == 1.0
    assert 0 < norm[1, 1] < 1


def test_decay_weights_recent_points():
    hm = HeatmapAccumulator(grid_w=4, grid_h=4, decay=0.5)
    hm.add_point(0.1, 0.1)
    hm.add_point(0.9, 0.9)
    assert hm.grid[3, 3] > hm.grid[0, 0]


def test_edge_points_clamped():
    hm = HeatmapAccumulator(grid_w=4, grid_h=4)
    hm.add_point(1.0, 1.0)
    assert hm.grid[3, 3] == 1.0
    assert np.isfinite(hm.grid).all()
