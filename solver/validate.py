from collections import Counter, defaultdict

from solver.types import BATCH, ROOM


def slot_label(grid, day, period):
    day_name = grid.days[day] if 0 <= day < len(grid.days) else f"day {day}"
    if 0 <= period < len(grid.periods):
        return f"{day_name} {grid.periods[period][0]}"
    return f"{day_name} period {period}"


def periods_of(placement, requirement):
    return tuple(range(placement.start, placement.start + requirement.length))


def per_day_limit(requirement, day_count):
    if requirement.sessions <= day_count:
        return 1
    return (requirement.sessions + day_count - 1) // day_count


def check_sessions(instance, placements):
    violations = []
    known = instance.requirement_map
    by_requirement = defaultdict(list)
    for placement in placements:
        if placement.requirement not in known:
            violations.append(f"Placement refers to unknown requirement {placement.requirement}")
            continue
        by_requirement[placement.requirement].append(placement.session)
    for requirement in instance.requirements:
        sessions = by_requirement.get(requirement.id, [])
        if len(sessions) != requirement.sessions:
            violations.append(
                f"{requirement.id} has {len(sessions)} placed sessions, expected "
                f"{requirement.sessions}"
            )
        if len(set(sessions)) != len(sessions):
            violations.append(f"{requirement.id} repeats a session number")
        for session in sessions:
            if not 0 <= session < requirement.sessions:
                violations.append(f"{requirement.id} has session number {session} out of range")
    return violations


def check_slot(grid, placement, requirement):
    if not 0 <= placement.day < len(grid.days):
        return [f"{requirement.id} session {placement.session} is on day {placement.day}"]
    periods = periods_of(placement, requirement)
    if periods[0] < 0 or periods[-1] >= len(grid.periods):
        return [
            f"{requirement.id} session {placement.session} runs past the grid at "
            f"{slot_label(grid, placement.day, placement.start)}"
        ]
    for block in grid.blocks:
        if periods[0] in block:
            if all(period in block for period in periods):
                return []
            return [
                f"{requirement.id} session {placement.session} crosses a break at "
                f"{slot_label(grid, placement.day, placement.start)}"
            ]
    return [f"{requirement.id} session {placement.session} starts outside every block"]


def check_fixed_slot(placement, requirement):
    if placement.session >= len(requirement.fixed_slots):
        return []
    wanted = requirement.fixed_slots[placement.session]
    if (placement.day, placement.start) == wanted:
        return []
    return [
        f"{requirement.id} session {placement.session} must be at day {wanted[0]} "
        f"period {wanted[1]} but is at day {placement.day} period {placement.start}"
    ]


def check_rooms(resource_map, placement, requirement):
    violations = []
    label = f"{requirement.id} session {placement.session}"
    rooms = placement.rooms
    if len(rooms) != requirement.rooms_needed:
        violations.append(f"{label} has {len(rooms)} rooms, needs {requirement.rooms_needed}")
    if len(set(rooms)) != len(rooms):
        violations.append(f"{label} uses the same room twice")
    for room_id in rooms:
        room = resource_map.get(room_id)
        if room is None:
            violations.append(f"{label} uses unknown room {room_id}")
        elif room.kind != ROOM:
            violations.append(f"{label} uses {room_id} which is not a room")
        elif requirement.room_tag is not None and requirement.room_tag not in room.tags:
            violations.append(f"{label} uses {room_id} which is not tagged {requirement.room_tag}")
    real_rooms = [resource_map[room_id] for room_id in rooms if room_id in resource_map]
    capacities = [
        resource_map[attendee].capacity
        for attendee in requirement.attendees
        if attendee in resource_map
    ]
    split = requirement.rooms_needed == len(requirement.attendees) > 1
    if split and len(real_rooms) == len(capacities):
        for attendee, room, needed in zip(
            requirement.attendees, real_rooms, capacities, strict=True
        ):
            if room.capacity < needed:
                violations.append(
                    f"{label} puts {attendee} ({needed}) in {room.id} ({room.capacity})"
                )
        for position, fixed in enumerate(requirement.fixed_rooms):
            if position < len(rooms) and rooms[position] != fixed:
                violations.append(f"{label} must use {fixed} for {requirement.attendees[position]}")
    elif requirement.rooms_needed > 0:
        needed = -(-sum(capacities) // requirement.rooms_needed)
        for room in real_rooms:
            if room.capacity < needed:
                violations.append(
                    f"{label} needs capacity {needed} but {room.id} holds {room.capacity}"
                )
        for fixed in requirement.fixed_rooms:
            if fixed not in rooms:
                violations.append(f"{label} must use fixed room {fixed}")
    return violations


def check_per_day(instance, placements):
    violations = []
    counts = Counter((placement.requirement, placement.day) for placement in placements)
    for (requirement_id, day), count in sorted(counts.items()):
        requirement = instance.requirement_map.get(requirement_id)
        if requirement is None:
            continue
        limit = per_day_limit(requirement, len(instance.grid.days))
        if count > limit:
            days = instance.grid.days
            day_name = days[day] if 0 <= day < len(days) else f"day {day}"
            violations.append(
                f"{requirement_id} has {count} sessions on {day_name}, at most {limit} allowed"
            )
    return violations


def check_occupancy(instance, placements):
    grid = instance.grid
    resource_map = instance.resource_map
    requirement_map = instance.requirement_map
    blocked = defaultdict(set)
    for resource_id, day, period in instance.blocked:
        blocked[resource_id].add((day, period))
    usage = defaultdict(list)
    load = Counter()
    violations = []
    for placement in placements:
        requirement = requirement_map.get(placement.requirement)
        if requirement is None or check_slot(grid, placement, requirement):
            continue
        label = f"{requirement.id} session {placement.session}"
        involved = dict.fromkeys(requirement.teachers + requirement.attendees + placement.rooms)
        for teacher in dict.fromkeys(requirement.teachers):
            load[teacher] += requirement.length
        for period in periods_of(placement, requirement):
            slot = (placement.day, period)
            for resource_id in involved:
                usage[resource_id, slot].append(label)
                resource = resource_map.get(resource_id)
                if resource is None:
                    continue
                if slot in resource.unavailable:
                    violations.append(
                        f"{resource_id} is unavailable at {slot_label(grid, *slot)} but has {label}"
                    )
                if slot in blocked.get(resource_id, ()):
                    violations.append(
                        f"{resource_id} is blocked at {slot_label(grid, *slot)} but has {label}"
                    )
    for (resource_id, slot), labels in sorted(usage.items()):
        if len(labels) > 1:
            violations.append(
                f"{resource_id} is double booked at {slot_label(grid, *slot)}: "
                f"{' and '.join(labels)}"
            )
    for resource in instance.resources:
        if resource.kind != BATCH or resource.parent is None:
            continue
        for (resource_id, slot), labels in usage.items():
            if resource_id != resource.id:
                continue
            clashes = usage.get((resource.parent, slot), [])
            if clashes:
                violations.append(
                    f"{resource.id} and its section {resource.parent} are both booked at "
                    f"{slot_label(grid, *slot)}: {labels[0]} and {clashes[0]}"
                )
    for teacher, periods in sorted(load.items()):
        resource = resource_map.get(teacher)
        if resource is not None and resource.max_load is not None and periods > resource.max_load:
            violations.append(
                f"{teacher} teaches {periods} periods, above the load limit of {resource.max_load}"
            )
    return violations


def validate(instance, placements):
    placements = tuple(placements)
    violations = check_sessions(instance, placements)
    resource_map = instance.resource_map
    requirement_map = instance.requirement_map
    for placement in placements:
        requirement = requirement_map.get(placement.requirement)
        if requirement is None:
            continue
        violations += check_slot(instance.grid, placement, requirement)
        violations += check_fixed_slot(placement, requirement)
        violations += check_rooms(resource_map, placement, requirement)
    violations += check_per_day(instance, placements)
    violations += check_occupancy(instance, placements)
    return violations
