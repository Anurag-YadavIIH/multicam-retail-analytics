"""Zone geometry: point-in-polygon on normalized coordinates.

Pure python ray-casting - no cv2 dependency, trivially unit-testable.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ZoneDef:
    id: int
    name: str
    type: str  # entrance | exit | aisle | shelf | queue | checkout | restricted
    polygon: tuple[tuple[float, float], ...]


def point_in_polygon(x: float, y: float, polygon: tuple[tuple[float, float], ...]) -> bool:
    """Ray casting algorithm. Polygon points in order (either winding)."""
    inside = False
    n = len(polygon)
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if (yi > y) != (yj > y):
            x_int = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < x_int:
                inside = not inside
        j = i
    return inside


def zones_containing(x: float, y: float, zones: list[ZoneDef]) -> list[ZoneDef]:
    return [z for z in zones if point_in_polygon(x, y, z.polygon)]
