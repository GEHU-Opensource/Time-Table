from collections import defaultdict

import ortools
from ortools.sat.python import cp_model

from solver.precheck import (
    candidate_rooms,
    children_of,
    closed_slots,
    covered_periods,
    participants,
    reference_errors,
    room_positions,
    rooms_at_position,
    sessions_per_day,
    splits_rooms,
)
from solver.types import (
    BATCH,
    FEASIBLE,
    INFEASIBLE,
    OPTIMAL,
    TEACHER,
    TOO_LARGE,
    UNKNOWN,
    Placement,
    Result,
)

STATUS = {
    cp_model.OPTIMAL: OPTIMAL,
    cp_model.FEASIBLE: FEASIBLE,
    cp_model.INFEASIBLE: INFEASIBLE,
    cp_model.UNKNOWN: UNKNOWN,
    cp_model.MODEL_INVALID: UNKNOWN,
}


def leaf_attendees(instance):
    children = children_of(instance)
    attendees = dict.fromkeys(
        attendee for requirement in instance.requirements for attendee in requirement.attendees
    )
    return tuple(attendee for attendee in attendees if not children.get(attendee))


def soft_weight_total(instance):
    slots = len(instance.grid.days) * len(instance.grid.periods)
    preferred = sum(
        len(resource.preferred) for resource in instance.resources if resource.kind == TEACHER
    )
    return preferred + slots * len(leaf_attendees(instance))


def estimate_booleans(instance):
    grid = instance.grid
    resource_map = instance.resource_map
    days = len(grid.days)
    total = 0
    for requirement in instance.requirements:
        slots = requirement.sessions * days * len(grid.starts_for(requirement.length))
        rooms = sum(
            len(candidate_rooms(instance, requirement, position, resource_map))
            for position in range(room_positions(requirement))
        )
        total += slots + requirement.sessions * rooms + slots * rooms + requirement.sessions * 2
    total += 4 * days * len(grid.periods) * len(leaf_attendees(instance))
    total += len(instance.hints)
    return total


class Build:
    def __init__(self, instance, relaxed):
        self.instance = instance
        self.relaxed = relaxed
        self.grid = instance.grid
        self.resource_map = instance.resource_map
        self.closed = closed_slots(instance)
        self.leaves = leaf_attendees(instance)
        self.model = cp_model.CpModel()
        self.slots_of = defaultdict(list)
        self.rooms_of = defaultdict(list)
        self.placed = {}
        self.occupancy = defaultdict(list)
        self.load = defaultdict(list)
        self.cost = []
        self.moved = {}
        self.hint_map = {(hint.requirement, hint.session): hint for hint in instance.hints}
        self.hint_weight = 1 + soft_weight_total(instance)
        for requirement in instance.requirements:
            self.add_requirement(requirement)
        self.add_occupancy()
        self.add_loads()
        self.add_gaps()
        self.add_objective()

    def slot_open(self, resource_id, day, start, length):
        closed = self.closed.get(resource_id, ())
        return not any((day, period) in closed for period in covered_periods(start, length))

    def forbid(self, requirement_id, session):
        self.model.Add(self.placed[requirement_id, session] == 0)

    def slot_literal(self, requirement_id, session, day, start):
        for slot_day, slot_start, literal in self.slots_of[requirement_id, session]:
            if (slot_day, slot_start) == (day, start):
                return literal
        return None

    def room_literal(self, requirement_id, session, position, room):
        for slot_position, slot_room, literal in self.rooms_of[requirement_id, session]:
            if (slot_position, slot_room) == (position, room):
                return literal
        return None

    def add_requirement(self, requirement):
        day_count = len(self.grid.days)
        period_count = len(self.grid.periods)
        starts = self.grid.starts_for(requirement.length)
        people = participants(requirement)
        teachers = tuple(dict.fromkeys(requirement.teachers))
        positions = []
        per_day = defaultdict(list)
        for session in range(requirement.sessions):
            placed = self.model.NewBoolVar(f"placed_{requirement.id}_{session}")
            self.placed[requirement.id, session] = placed
            if not self.relaxed:
                self.model.Add(placed == 1)
            literals = []
            position_terms = []
            for day in range(day_count):
                for start in starts:
                    if not all(
                        self.slot_open(person, day, start, requirement.length) for person in people
                    ):
                        continue
                    literal = self.model.NewBoolVar(f"x_{requirement.id}_{session}_{day}_{start}")
                    self.slots_of[requirement.id, session].append((day, start, literal))
                    literals.append(literal)
                    per_day[day].append(literal)
                    position_terms.append((day * period_count + start) * literal)
                    for person in people:
                        for period in covered_periods(start, requirement.length):
                            self.occupancy[person, day, period].append(literal)
                    for teacher in teachers:
                        self.load[teacher].append(requirement.length * literal)
                        preferred = self.resource_map[teacher].preferred
                        reward = sum(
                            (day, period) in preferred
                            for period in covered_periods(start, requirement.length)
                        )
                        if reward:
                            self.cost.append(-reward * literal)
            self.model.Add(sum(literals) == placed)
            position = self.model.NewIntVar(0, day_count * period_count, "")
            self.model.Add(position == sum(position_terms))
            positions.append(position)
            self.pin_session(requirement, session)
            self.add_rooms(requirement, session)
            self.add_hint(requirement, session)
        cap = sessions_per_day(requirement, day_count)
        for day_literals in per_day.values():
            if len(day_literals) > cap:
                self.model.Add(sum(day_literals) <= cap)
        for session in range(len(requirement.fixed_slots) + 1, requirement.sessions):
            later = self.placed[requirement.id, session]
            ordered = self.model.Add(positions[session - 1] + 1 <= positions[session])
            if self.relaxed:
                self.model.Add(self.placed[requirement.id, session - 1] >= later)
                ordered.OnlyEnforceIf(later)

    def pin_session(self, requirement, session):
        if session >= len(requirement.fixed_slots):
            return
        day, start = requirement.fixed_slots[session]
        literal = self.slot_literal(requirement.id, session, day, start)
        if literal is None:
            self.forbid(requirement.id, session)
        else:
            self.model.Add(literal == 1).OnlyEnforceIf(self.placed[requirement.id, session])

    def add_rooms(self, requirement, session):
        placed = self.placed[requirement.id, session]
        used = defaultdict(list)
        for position in range(room_positions(requirement)):
            candidates = candidate_rooms(self.instance, requirement, position, self.resource_map)
            literals = []
            for room in candidates:
                literal = self.model.NewBoolVar(f"y_{requirement.id}_{session}_{position}_{room}")
                self.rooms_of[requirement.id, session].append((position, room, literal))
                literals.append(literal)
                used[room].append(literal)
                self.add_room_occupancy(requirement, session, literal, room)
            self.model.Add(sum(literals) == rooms_at_position(requirement, position) * placed)
            if splits_rooms(requirement):
                fixed = requirement.fixed_rooms[position : position + 1]
            else:
                fixed = requirement.fixed_rooms
            for room in fixed:
                literal = self.room_literal(requirement.id, session, position, room)
                if literal is None:
                    self.forbid(requirement.id, session)
                else:
                    self.model.Add(literal == 1).OnlyEnforceIf(placed)
        for literals in used.values():
            if len(literals) > 1:
                self.model.AddAtMostOne(literals)

    def add_room_occupancy(self, requirement, session, room_literal, room):
        for day, start, literal in self.slots_of[requirement.id, session]:
            if not self.slot_open(room, day, start, requirement.length):
                self.model.AddBoolOr([literal.Not(), room_literal.Not()])
                continue
            both = self.model.NewBoolVar("")
            self.model.AddBoolOr([literal.Not(), room_literal.Not(), both])
            self.model.AddImplication(both, literal)
            self.model.AddImplication(both, room_literal)
            for period in covered_periods(start, requirement.length):
                self.occupancy[room, day, period].append(both)

    def add_hint(self, requirement, session):
        hint = self.hint_map.get((requirement.id, session))
        if hint is None:
            return
        moved = self.model.NewBoolVar(f"moved_{requirement.id}_{session}")
        self.moved[requirement.id, session] = moved
        wanted = [self.slot_literal(requirement.id, session, hint.day, hint.start)]
        if splits_rooms(requirement):
            wanted.extend(
                self.room_literal(requirement.id, session, position, room)
                for position, room in enumerate(hint.rooms)
            )
        else:
            wanted.extend(
                self.room_literal(requirement.id, session, 0, room) for room in hint.rooms
            )
        for literal in wanted:
            if literal is None:
                self.model.Add(moved == 1)
            else:
                self.model.AddHint(literal, 1)
                self.model.AddImplication(literal.Not(), moved)
        self.cost.append(self.hint_weight * moved)

    def add_occupancy(self):
        for (resource_id, _day, _period), literals in self.occupancy.items():
            resource = self.resource_map.get(resource_id)
            if resource is not None and resource.kind == BATCH:
                continue
            if len(literals) > 1:
                self.model.AddAtMostOne(literals)
        for resource in self.instance.resources:
            if resource.kind != BATCH:
                continue
            for day, period in self.grid.slots():
                literals = self.attendee_literals(resource.id, day, period)
                if len(literals) > 1:
                    self.model.AddAtMostOne(literals)

    def add_loads(self):
        for teacher, terms in self.load.items():
            max_load = self.resource_map[teacher].max_load
            if max_load is not None:
                self.model.Add(sum(terms) <= max_load)

    def attendee_literals(self, attendee, day, period):
        literals = list(self.occupancy.get((attendee, day, period), []))
        parent = self.resource_map[attendee].parent
        if parent is not None:
            literals.extend(self.occupancy.get((parent, day, period), []))
        return literals

    def add_gaps(self):
        period_count = len(self.grid.periods)
        for attendee in self.leaves:
            for day in range(len(self.grid.days)):
                occupied = []
                for period in range(period_count):
                    literals = self.attendee_literals(attendee, day, period)
                    if not literals:
                        occupied.append(None)
                        continue
                    literal = self.model.NewBoolVar("")
                    self.model.Add(sum(literals) == literal)
                    occupied.append(literal)
                if sum(literal is not None for literal in occupied) < 2:
                    continue
                before, after = [], []
                for period in range(period_count):
                    has_before = self.model.NewBoolVar("")
                    for earlier in occupied[: period + 1]:
                        if earlier is not None:
                            self.model.AddImplication(earlier, has_before)
                    before.append(has_before)
                    has_after = self.model.NewBoolVar("")
                    for later in occupied[period:]:
                        if later is not None:
                            self.model.AddImplication(later, has_after)
                    after.append(has_after)
                for period in range(1, period_count - 1):
                    gap = self.model.NewBoolVar("")
                    terms = [before[period], after[period]]
                    if occupied[period] is not None:
                        terms.append(-occupied[period])
                    self.model.Add(gap >= sum(terms) - 1)
                    self.cost.append(gap)

    def add_objective(self):
        if self.relaxed:
            self.model.Maximize(sum(self.placed.values()))
        elif self.cost:
            self.model.Minimize(sum(self.cost))

    def run(self):
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.instance.max_seconds
        solver.parameters.num_workers = self.instance.workers
        solver.parameters.random_seed = self.instance.seed
        status = solver.Solve(self.model)
        return solver, STATUS.get(status, UNKNOWN)

    def stats(self, solver, status):
        solved = status in {OPTIMAL, FEASIBLE}
        return {
            "status": status,
            "objective": solver.ObjectiveValue() if solved and self.model.has_objective() else 0,
            "wall_time": solver.WallTime(),
            "num_conflicts": solver.NumConflicts(),
            "num_branches": solver.NumBranches(),
            "booleans": len(self.model.proto.variables),
            "ortools": ortools.__version__,
            "seed": self.instance.seed,
            "workers": self.instance.workers,
            "max_seconds": self.instance.max_seconds,
        }

    def placements(self, solver):
        placements = []
        for requirement in self.instance.requirements:
            for session in range(requirement.sessions):
                if not solver.Value(self.placed[requirement.id, session]):
                    continue
                day, start = next(
                    (day, start)
                    for day, start, literal in self.slots_of[requirement.id, session]
                    if solver.Value(literal)
                )
                rooms = tuple(
                    room
                    for _position, room, literal in self.rooms_of[requirement.id, session]
                    if solver.Value(literal)
                )
                placements.append(Placement(requirement.id, session, day, start, rooms))
        return tuple(placements)


def solve(instance):
    errors = reference_errors(instance)
    if errors:
        return Result(status=INFEASIBLE, reasons=tuple(errors))
    estimate = estimate_booleans(instance)
    if estimate > instance.max_model_size:
        return Result(
            status=TOO_LARGE,
            reasons=(
                f"Model needs about {estimate} booleans, above the limit of "
                f"{instance.max_model_size}",
            ),
            stats={"booleans": estimate},
        )
    build = Build(instance, relaxed=False)
    solver, status = build.run()
    stats = build.stats(solver, status)
    if status in {OPTIMAL, FEASIBLE}:
        return Result(status=status, placements=build.placements(solver), stats=stats)
    return Result(status=status, stats=stats)
