from analytics.zones import ZoneDef, point_in_polygon, zones_containing

SQUARE = ((0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8))


def test_point_inside():
    assert point_in_polygon(0.5, 0.5, SQUARE)


def test_point_outside():
    assert not point_in_polygon(0.1, 0.1, SQUARE)
    assert not point_in_polygon(0.9, 0.5, SQUARE)


def test_point_near_edge():
    assert point_in_polygon(0.21, 0.5, SQUARE)
    assert not point_in_polygon(0.81, 0.5, SQUARE)


def test_triangle():
    tri = ((0.0, 0.0), (1.0, 0.0), (0.0, 1.0))
    assert point_in_polygon(0.2, 0.2, tri)
    assert not point_in_polygon(0.9, 0.9, tri)


def test_zones_containing():
    zones = [
        ZoneDef(1, "queue", "queue", SQUARE),
        ZoneDef(2, "everything", "aisle", ((0, 0), (1, 0), (1, 1), (0, 1))),
    ]
    hits = zones_containing(0.5, 0.5, zones)
    assert {z.name for z in hits} == {"queue", "everything"}
    hits = zones_containing(0.05, 0.05, zones)
    assert {z.name for z in hits} == {"everything"}
