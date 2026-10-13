"""Bilinear Z-interpolation bed levelling mesh compensation (P6-1).

Adjusts pen contact Z-heights across measured bed topography (e.g. from Marlin G29 / M420 bilinear mesh).
Compensates for glass bed tilts, micro-warps, and clamp deflections to guarantee uniform pen pressure.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from penpress.core.primitives import CoreGeometryError, Point, Stroke


class MeshInterpolationError(CoreGeometryError):
    """Raised when coordinates fall outside the bed mesh bounds or mesh is invalid."""


@dataclass(frozen=True, slots=True)
class BedMeshGrid:
    """Represents a uniform rectangular bed levelling elevation grid.

    Attributes:
        x_min_mm: Minimum X boundary of mesh in mm.
        x_max_mm: Maximum X boundary of mesh in mm.
        y_min_mm: Minimum Y boundary of mesh in mm.
        y_max_mm: Maximum Y boundary of mesh in mm.
        x_count: Number of sample grid points along X (>= 2).
        y_count: Number of sample grid points along Y (>= 2).
        z_values: Row-major 2D tuple or flat tuple of Z elevation offsets in mm (size = x_count * y_count).
    """

    x_min_mm: float
    x_max_mm: float
    y_min_mm: float
    y_max_mm: float
    x_count: int
    y_count: int
    z_values: tuple[float, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.x_count < 2 or self.y_count < 2:
            raise MeshInterpolationError(
                f"Mesh grid must have at least 2x2 points, got {self.x_count}x{self.y_count}"
            )
        if self.x_min_mm >= self.x_max_mm or self.y_min_mm >= self.y_max_mm:
            bounds_msg = (
                f"Invalid mesh bounds: X [{self.x_min_mm}, {self.x_max_mm}], "
                f"Y [{self.y_min_mm}, {self.y_max_mm}]"
            )
            raise MeshInterpolationError(bounds_msg)
        expected_size = self.x_count * self.y_count
        if len(self.z_values) != expected_size:
            raise MeshInterpolationError(f"Expected {expected_size} Z mesh values, got {len(self.z_values)}")
        for z in self.z_values:
            if not math.isfinite(z):
                raise MeshInterpolationError(f"Z mesh elevation must be finite number, got {z}")

    @property
    def dx(self) -> float:
        return (self.x_max_mm - self.x_min_mm) / (self.x_count - 1)

    @property
    def dy(self) -> float:
        return (self.y_max_mm - self.y_min_mm) / (self.y_count - 1)

    def get_grid_z(self, ix: int, iy: int) -> float:
        """Get Z value at integer grid coordinate."""
        if not (0 <= ix < self.x_count and 0 <= iy < self.y_count):
            raise IndexError(f"Grid coordinate ({ix}, {iy}) out of range")
        return self.z_values[iy * self.x_count + ix]

    def interpolate_z(self, x: float, y: float, clamp_boundary: bool = True) -> float:
        """Compute bilinear interpolated Z elevation offset at (x, y).

        Args:
            x: X-coordinate in mm.
            y: Y-coordinate in mm.
            clamp_boundary: If True, clamps out-of-bounds queries to the mesh edge; otherwise raises error.

        Returns:
            Interpolated Z offset in mm.
        """
        if not math.isfinite(x) or not math.isfinite(y):
            raise MeshInterpolationError(f"Coordinates must be finite, got ({x}, {y})")

        if not (self.x_min_mm <= x <= self.x_max_mm and self.y_min_mm <= y <= self.y_max_mm):
            if not clamp_boundary:
                raise MeshInterpolationError(
                    f"Coordinate ({x:.2f}, {y:.2f}) outside mesh boundaries "
                    f"[{self.x_min_mm}..{self.x_max_mm}, {self.y_min_mm}..{self.y_max_mm}]"
                )
            x = max(self.x_min_mm, min(self.x_max_mm, x))
            y = max(self.y_min_mm, min(self.y_max_mm, y))

        # Normalized coordinates within grid cell
        u = (x - self.x_min_mm) / self.dx
        v = (y - self.y_min_mm) / self.dy

        ix = math.floor(u)
        iy = math.floor(v)

        # Handle top/right border points
        if ix >= self.x_count - 1:
            ix = self.x_count - 2
        if iy >= self.y_count - 1:
            iy = self.y_count - 2

        # Relative fractions in [0, 1]
        tx = max(0.0, min(1.0, (x - (self.x_min_mm + ix * self.dx)) / self.dx))
        ty = max(0.0, min(1.0, (y - (self.y_min_mm + iy * self.dy)) / self.dy))

        # Four cell corner Z values
        z00 = self.get_grid_z(ix, iy)
        z10 = self.get_grid_z(ix + 1, iy)
        z01 = self.get_grid_z(ix, iy + 1)
        z11 = self.get_grid_z(ix + 1, iy + 1)

        # Bilinear interpolation
        z_bottom = z00 * (1.0 - tx) + z10 * tx
        z_top = z01 * (1.0 - tx) + z11 * tx
        return z_bottom * (1.0 - ty) + z_top * ty

    @classmethod
    def from_analytical_plane(
        cls,
        x_min: float,
        x_max: float,
        y_min: float,
        y_max: float,
        x_count: int,
        y_count: int,
        slope_x: float,
        slope_y: float,
        z_origin: float = 0.0,
    ) -> BedMeshGrid:
        """Create a mesh representing an exact tilted plane z = z_origin + slope_x * x + slope_y * y."""
        dx = (x_max - x_min) / (x_count - 1)
        dy = (y_max - y_min) / (y_count - 1)
        z_vals: list[float] = []
        for iy in range(y_count):
            y = y_min + iy * dy
            for ix in range(x_count):
                x = x_min + ix * dx
                z_vals.append(z_origin + slope_x * x + slope_y * y)
        return cls(
            x_min_mm=x_min,
            x_max_mm=x_max,
            y_min_mm=y_min,
            y_max_mm=y_max,
            x_count=x_count,
            y_count=y_count,
            z_values=tuple(z_vals),
        )


class BedMeshCompensator:
    """Applies bed levelling Z-compensation to strokes and machine coordinates."""

    def __init__(self, mesh: BedMeshGrid) -> None:
        self.mesh = mesh

    def compute_compensated_z(self, x: float, y: float, nominal_z: float) -> float:
        """Compute the adjusted Z height at (x, y) taking bed mesh elevation into account."""
        z_offset = self.mesh.interpolate_z(x, y)
        return nominal_z + z_offset

    def compensate_stroke(self, stroke: Stroke, base_z_mm: float) -> list[tuple[Point, float]]:
        """Return list of (Point, compensated_z_mm) pairs for each point in the stroke."""
        result: list[tuple[Point, float]] = []
        for pt in stroke.points:
            z = self.compute_compensated_z(pt.x, pt.y, base_z_mm)
            result.append((pt, z))
        return result
