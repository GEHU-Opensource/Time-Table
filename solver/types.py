from dataclasses import dataclass, field

TEACHER = "teacher"
ROOM = "room"
SECTION = "section"
BATCH = "batch"

OPTIMAL = "optimal"
FEASIBLE = "feasible"
INFEASIBLE = "infeasible"
UNKNOWN = "unknown"
TOO_LARGE = "too_large"


def to_minutes(clock):
    hours, minutes = clock.split(":")
    return int(hours) * 60 + int(minutes)


@dataclass(frozen=True)
class Grid:
    days: tuple[str, ...]
    periods: tuple[tuple[str, str], ...]
    breaks_after: frozenset[int] = frozenset()

    @classmethod
    def from_json(cls, data):
        return cls(
            days=tuple(data["days"]),
            periods=tuple((start, end) for start, end in data["periods"]),
            breaks_after=frozenset(int(index) for index in data.get("breaks_after", [])),
        )

    def to_json(self):
        return {
            "days": list(self.days),
            "periods": [list(period) for period in self.periods],
            "breaks_after": sorted(self.breaks_after),
        }

    @property
    def blocks(self):
        blocks, current = [], []
        for index in range(len(self.periods)):
            current.append(index)
            if index in self.breaks_after:
                blocks.append(tuple(current))
                current = []
        if current:
            blocks.append(tuple(current))
        return tuple(blocks)

    def block_of(self, period):
        for block in self.blocks:
            if period in block:
                return block
        raise ValueError(f"period {period} outside grid")

    def starts_for(self, length):
        return tuple(
            block[offset] for block in self.blocks for offset in range(len(block) - length + 1)
        )

    def minutes(self, period):
        start, end = self.periods[period]
        return to_minutes(start), to_minutes(end)

    def overlapping(self, start_minute, end_minute):
        return tuple(
            index
            for index in range(len(self.periods))
            if self.minutes(index)[0] < end_minute and self.minutes(index)[1] > start_minute
        )

    def slots(self):
        return tuple(
            (day, period) for day in range(len(self.days)) for period in range(len(self.periods))
        )


@dataclass(frozen=True)
class Resource:
    id: str
    kind: str
    capacity: int = 0
    tags: frozenset[str] = frozenset()
    max_load: int | None = None
    unavailable: frozenset[tuple[int, int]] = frozenset()
    preferred: frozenset[tuple[int, int]] = frozenset()
    parent: str | None = None


@dataclass(frozen=True)
class Requirement:
    id: str
    subject: str
    length: int
    sessions: int
    teachers: tuple[str, ...]
    attendees: tuple[str, ...]
    rooms_needed: int = 1
    room_tag: str | None = None
    fixed_rooms: tuple[str, ...] = ()
    fixed_slots: tuple[tuple[int, int], ...] = ()


@dataclass(frozen=True)
class Placement:
    requirement: str
    session: int
    day: int
    start: int
    rooms: tuple[str, ...] = ()


@dataclass(frozen=True)
class Instance:
    grid: Grid
    resources: tuple[Resource, ...]
    requirements: tuple[Requirement, ...]
    blocked: frozenset[tuple[str, int, int]] = frozenset()
    hints: tuple[Placement, ...] = ()
    max_seconds: float = 120.0
    workers: int = 4
    seed: int = 0
    max_model_size: int = 5_000_000

    def resource(self, resource_id):
        return self.resource_map[resource_id]

    @property
    def resource_map(self):
        return {resource.id: resource for resource in self.resources}

    @property
    def requirement_map(self):
        return {requirement.id: requirement for requirement in self.requirements}


@dataclass(frozen=True)
class Result:
    status: str
    placements: tuple[Placement, ...] = ()
    unplaced: tuple[tuple[str, int], ...] = ()
    reasons: tuple[str, ...] = ()
    stats: dict = field(default_factory=dict)

    @property
    def solved(self):
        return self.status in {OPTIMAL, FEASIBLE}
