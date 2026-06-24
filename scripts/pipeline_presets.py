from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class PipelinePreset:
    frame_step: int
    sequential_overlap: int
    iterations: int
    sugar_mode: str
    sugar_refinement_time: str
    run_sugar: bool

    def as_dict(self) -> dict[str, bool | int | str]:
        return asdict(self)


PRESETS = {
    "fast": PipelinePreset(
        frame_step=4,
        sequential_overlap=10,
        iterations=1000,
        sugar_mode="low",
        sugar_refinement_time="short",
        run_sugar=False,
    ),
    "balanced": PipelinePreset(
        frame_step=2,
        sequential_overlap=20,
        iterations=7000,
        sugar_mode="default",
        sugar_refinement_time="medium",
        run_sugar=True,
    ),
    "quality": PipelinePreset(
        frame_step=1,
        sequential_overlap=40,
        iterations=30000,
        sugar_mode="high",
        sugar_refinement_time="long",
        run_sugar=True,
    ),
}
