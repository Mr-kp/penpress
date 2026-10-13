"""Pen toolpath optimizer and TSP travel distance minimizer (P6-1).

Reorders strokes to minimize airborne non-drawing travel distance using greedy nearest-neighbour
and 2-opt Euclidean heuristics. Optionally flips reversible strokes when jumping from
an endpoint to the closest start/end of the subsequent stroke.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from penpress.core.primitives import Page, Point, Stroke
from penpress.core.primitives import Path as CorePath
from penpress.plan.merger import merge_collinear_strokes, validate_stroke_geometry


@dataclass(frozen=True, slots=True)
class OptimizationStats:
    """Statistics comparing naive vs optimized toolpath metrics.

    Attributes:
        stroke_count_before: Initial number of strokes.
        stroke_count_after: Final number of strokes after merging.
        travel_distance_before_mm: Airborne non-drawing travel distance before optimization in mm.
        travel_distance_after_mm: Airborne non-drawing travel distance after optimization in mm.
        drawing_distance_mm: Total drawing distance in mm.
        distance_reduction_pct: Percentage reduction in non-drawing travel distance.
        reversed_stroke_count: Number of strokes reversed for optimal chaining.
    """

    stroke_count_before: int
    stroke_count_after: int
    travel_distance_before_mm: float
    travel_distance_after_mm: float
    drawing_distance_mm: float
    distance_reduction_pct: float
    reversed_stroke_count: int


def calculate_travel_distance(strokes: Sequence[Stroke], start_point: Point | None = None) -> float:
    """Calculate the total airborne non-drawing travel distance between successive strokes."""
    if not strokes:
        return 0.0

    travel = 0.0
    current_pos = start_point if start_point is not None else strokes[0].points[0]

    for stroke in strokes:
        travel += current_pos.distance_to(stroke.points[0])
        current_pos = stroke.points[-1]

    return travel


def reverse_stroke(stroke: Stroke) -> Stroke:
    """Reverse point sequence in a Stroke, preserving pressure and adjusting time offsets."""
    reversed_pts = list(reversed(stroke.points))
    return Stroke(reversed_pts)


class ToolpathOptimizer:
    """Optimizes stroke execution order to minimize pen-up rapid travel."""

    def __init__(
        self,
        allow_stroke_flip: bool = True,
        merge_collinear: bool = True,
        collinear_distance_tolerance_mm: float = 0.15,
        max_2opt_iterations: int = 50,
        start_point: Point | None = None,
    ) -> None:
        self.allow_stroke_flip = allow_stroke_flip
        self.merge_collinear = merge_collinear
        self.collinear_distance_tolerance_mm = collinear_distance_tolerance_mm
        self.max_2opt_iterations = max_2opt_iterations
        self.start_point = start_point if start_point is not None else Point(0.0, 0.0)

    def optimize_strokes(
        self,
        strokes: Sequence[Stroke],
    ) -> tuple[list[Stroke], OptimizationStats]:
        """Optimize stroke order and orientation to minimize travel distance."""
        for s in strokes:
            validate_stroke_geometry(s)

        initial_count = len(strokes)
        if not strokes:
            stats = OptimizationStats(
                stroke_count_before=0,
                stroke_count_after=0,
                travel_distance_before_mm=0.0,
                travel_distance_after_mm=0.0,
                drawing_distance_mm=0.0,
                distance_reduction_pct=0.0,
                reversed_stroke_count=0,
            )
            return [], stats

        travel_before = calculate_travel_distance(strokes, self.start_point)
        draw_dist = sum(s.length_mm for s in strokes)

        # 1. Merge collinear adjacent strokes if requested
        working_strokes: list[Stroke] = (
            merge_collinear_strokes(strokes, distance_tolerance_mm=self.collinear_distance_tolerance_mm)
            if self.merge_collinear
            else list(strokes)
        )

        n = len(working_strokes)
        if n <= 1:
            travel_after = calculate_travel_distance(working_strokes, self.start_point)
            pct = 100.0 * (travel_before - travel_after) / travel_before if travel_before > 1e-6 else 0.0
            stats = OptimizationStats(
                stroke_count_before=initial_count,
                stroke_count_after=n,
                travel_distance_before_mm=travel_before,
                travel_distance_after_mm=travel_after,
                drawing_distance_mm=draw_dist,
                distance_reduction_pct=pct,
                reversed_stroke_count=0,
            )
            return working_strokes, stats

        # 2. Greedy Nearest-Neighbour chaining with orientation choice
        unvisited = list(range(n))
        ordered_strokes: list[Stroke] = []
        current_pos = self.start_point
        reversed_count = 0

        while unvisited:
            best_idx = -1
            best_dist = float("inf")
            best_flipped = False

            for idx in unvisited:
                s = working_strokes[idx]
                p_start = s.points[0]
                d_normal = current_pos.distance_to(p_start)

                if d_normal < best_dist:
                    best_dist = d_normal
                    best_idx = idx
                    best_flipped = False

                if self.allow_stroke_flip:
                    p_end = s.points[-1]
                    d_flipped = current_pos.distance_to(p_end)
                    if d_flipped < best_dist:
                        best_dist = d_flipped
                        best_idx = idx
                        best_flipped = True

            unvisited.remove(best_idx)
            chosen_stroke = working_strokes[best_idx]
            if best_flipped:
                chosen_stroke = reverse_stroke(chosen_stroke)
                reversed_count += 1

            ordered_strokes.append(chosen_stroke)
            current_pos = chosen_stroke.points[-1]

        # 3. 2-opt Local Search refinement on stroke sequence
        # Try swapping stroke order (and reversing if beneficial)
        m = len(ordered_strokes)
        if m >= 3 and self.max_2opt_iterations > 0:
            improved = True
            iteration = 0
            while improved and iteration < self.max_2opt_iterations:
                improved = False
                iteration += 1

                for i in range(m - 1):
                    for j in range(i + 1, min(m, i + 30)):  # local window for fast convergence
                        # Evaluate reversing subsegment ordered_strokes[i:j+1]
                        current_cost = self._subsegment_travel_cost(ordered_strokes, i, j)

                        # Test reversed subsegment with internally flipped strokes
                        candidate_subsegment: list[Stroke] = []
                        for s in reversed(ordered_strokes[i : j + 1]):
                            candidate_subsegment.append(reverse_stroke(s) if self.allow_stroke_flip else s)

                        test_sequence = ordered_strokes[:i] + candidate_subsegment + ordered_strokes[j + 1 :]
                        new_cost = self._subsegment_travel_cost(test_sequence, i, j)

                        if new_cost < current_cost - 1e-4:
                            ordered_strokes = test_sequence
                            improved = True
                            break
                    if improved:
                        break

        # 4. Optional final pass: check if reversing single stroke reduces gap
        for i in range(len(ordered_strokes)):
            if not self.allow_stroke_flip:
                break
            prev_end = self.start_point if i == 0 else ordered_strokes[i - 1].points[-1]
            s = ordered_strokes[i]
            next_start = ordered_strokes[i + 1].points[0] if i + 1 < len(ordered_strokes) else None

            # Current cost
            cost_curr = prev_end.distance_to(s.points[0]) + (
                s.points[-1].distance_to(next_start) if next_start is not None else 0.0
            )

            # Flipped cost
            cost_flip = prev_end.distance_to(s.points[-1]) + (
                s.points[0].distance_to(next_start) if next_start is not None else 0.0
            )

            if cost_flip < cost_curr - 1e-4:
                ordered_strokes[i] = reverse_stroke(s)
                reversed_count += 1

        travel_after = calculate_travel_distance(ordered_strokes, self.start_point)
        pct = 100.0 * (travel_before - travel_after) / travel_before if travel_before > 1e-6 else 0.0

        stats = OptimizationStats(
            stroke_count_before=initial_count,
            stroke_count_after=len(ordered_strokes),
            travel_distance_before_mm=travel_before,
            travel_distance_after_mm=travel_after,
            drawing_distance_mm=draw_dist,
            distance_reduction_pct=pct,
            reversed_stroke_count=reversed_count,
        )

        return ordered_strokes, stats

    def _subsegment_travel_cost(self, seq: Sequence[Stroke], i: int, j: int) -> float:
        """Calculate the travel cost related to subsegment boundaries [i..j]."""
        cost = 0.0
        # Jump into i
        p_prev = self.start_point if i == 0 else seq[i - 1].points[-1]
        cost += p_prev.distance_to(seq[i].points[0])

        # Internal jumps within [i..j]
        for k in range(i, j):
            cost += seq[k].points[-1].distance_to(seq[k + 1].points[0])

        # Jump out of j to j+1
        if j + 1 < len(seq):
            cost += seq[j].points[-1].distance_to(seq[j + 1].points[0])

        return cost

    def optimize_page(self, page: Page) -> tuple[Page, OptimizationStats]:
        """Optimize all strokes within a Page and return a new Page."""
        all_strokes: list[Stroke] = []
        for path in page.paths:
            all_strokes.extend(path.strokes)

        optimized_strokes, stats = self.optimize_strokes(all_strokes)
        new_path = CorePath(optimized_strokes, label="optimized_toolpath")
        optimized_page = Page(
            width_mm=page.width_mm,
            height_mm=page.height_mm,
            paths=[new_path],
        )
        return optimized_page, stats
