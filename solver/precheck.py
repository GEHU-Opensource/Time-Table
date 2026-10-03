from collections import defaultdict

from solver.types import BATCH, ROOM, SECTION, TEACHER


def ceil_div(numerator, denominator):
    return -(-numerator // denominator)


def sessions_per_day(requirement, day_count):
    if requirement.sessions <= day_count:
        return 1
    return ceil_div(requirement.sessions, day_count)


def splits_rooms(requirement):
    return requirement.rooms_needed == len(requirement.attendees) > 1


def room_positions(requirement):
    if requirement.rooms_needed == 0:
        return 0
    if splits_rooms(requirement):
        return requirement.rooms_needed
    return 1


def rooms_at_position(requirement, position):
    if splits_rooms(requirement):
        return 1
    return requirement.rooms_needed


def capacity_needed(resource_map, requirement, position):
    capacities = [
        resource_map[attendee].capacity
        for attendee in requirement.attendees
        if attendee in resource_map
    ]
    if requirement.rooms_needed == 0:
        return 0
    if splits_rooms(requirement):
        return capacities[position] if position < len(capacities) else 0
    return ceil_div(sum(capacities), requirement.rooms_needed)


def room_fits(room, requirement, needed):
    if room.kind != ROOM:
        return False
    if requirement.room_tag is not None and requirement.room_tag not in room.tags:
        return False
    return room.capacity >= needed


def candidate_rooms(instance, requirement, position, resource_map=None):
    resource_map = resource_map or instance.resource_map
    needed = capacity_needed(resource_map, requirement, position)
    return tuple(
        resource.id for resource in instance.resources if room_fits(resource, requirement, needed)
    )


def participants(requirement):
    return tuple(dict.fromkeys(requirement.teachers + requirement.attendees))


def covered_periods(start, length):
    return range(start, start + length)


def children_of(instance):
    children = defaultdict(list)
    for resource in instance.resources:
        if resource.parent is not None:
            children[resource.parent].append(resource.id)
    return children


def closed_slots(instance):
    closed = defaultdict(set)
    for resource_id, day, period in instance.blocked:
        closed[resource_id].add((day, period))
    for resource in instance.resources:
        closed[resource.id].update(resource.unavailable)
    return closed


def describe_rooms(requirement, needed):
    tag = f" tagged {requirement.room_tag}" if requirement.room_tag else ""
    return f"a room{tag} with capacity >= {needed}"


def reference_errors(instance):
    resource_map = instance.resource_map
    errors = []
    for requirement in instance.requirements:
        if not isinstance(requirement.subject, str) or not requirement.subject.strip():
            errors.append(f"Requirement {requirement.id} has no subject")
        if not requirement.attendees:
            errors.append(f"Requirement {requirement.id} has no attendees")
        if requirement.length < 1 or requirement.sessions < 1:
            errors.append(f"Requirement {requirement.id} needs a positive length and session count")
        for teacher in requirement.teachers:
            if teacher not in resource_map:
                errors.append(f"Requirement {requirement.id} references unknown teacher {teacher}")
            elif resource_map[teacher].kind != TEACHER:
                errors.append(f"Requirement {requirement.id} lists {teacher} as a teacher")
        for attendee in requirement.attendees:
            if attendee not in resource_map:
                errors.append(
                    f"Requirement {requirement.id} references unknown attendee {attendee}"
                )
            elif resource_map[attendee].kind not in {SECTION, BATCH}:
                errors.append(f"Requirement {requirement.id} lists {attendee} as an attendee")
        for room in requirement.fixed_rooms:
            if room not in resource_map:
                errors.append(f"Requirement {requirement.id} references unknown room {room}")
            elif resource_map[room].kind != ROOM:
                errors.append(f"Requirement {requirement.id} lists {room} as a room")
    for resource_id, _day, _period in instance.blocked:
        if resource_id not in resource_map:
            errors.append(f"Blocked slot references unknown resource {resource_id}")
    return errors


def hierarchy_errors(instance):
    resource_map = instance.resource_map
    errors = []
    for resource in instance.resources:
        if resource.kind == BATCH:
            parent = resource_map.get(resource.parent)
            if parent is None:
                errors.append(f"Batch {resource.id} has no parent section")
            elif parent.kind != SECTION:
                errors.append(f"Batch {resource.id} has parent {parent.id} which is not a section")
        elif resource.parent is not None:
            errors.append(f"{resource.kind.title()} {resource.id} must not have a parent")
    return errors


def grid_errors(instance):
    grid = instance.grid
    errors = []
    for requirement in instance.requirements:
        starts = grid.starts_for(requirement.length)
        if not starts:
            errors.append(
                f"Requirement {requirement.id} length {requirement.length} fits in no block"
            )
        if len(requirement.fixed_slots) > requirement.sessions:
            errors.append(
                f"Requirement {requirement.id} fixes {len(requirement.fixed_slots)} slots "
                f"but has {requirement.sessions} sessions"
            )
        for day, start in requirement.fixed_slots:
            if not 0 <= day < len(grid.days):
                errors.append(f"Requirement {requirement.id} fixes day {day} outside the grid")
            elif start not in starts:
                errors.append(
                    f"Requirement {requirement.id} fixes a session at day {day} period {start} "
                    f"that does not fit in one block"
                )
    return errors


def fixed_collision_errors(instance):
    resource_map = instance.resource_map
    taken = defaultdict(list)
    for requirement in instance.requirements:
        people = list(participants(requirement))
        for attendee in requirement.attendees:
            parent = getattr(resource_map.get(attendee), "parent", None)
            if parent is not None:
                people.append(parent)
        for day, start in requirement.fixed_slots:
            for period in covered_periods(start, requirement.length):
                for person in dict.fromkeys(people):
                    taken[person, day, period].append(requirement.id)
    errors = []
    for (person, day, period), requirement_ids in sorted(taken.items()):
        if len(requirement_ids) > 1:
            errors.append(
                f"{person} has fixed sessions of {' and '.join(requirement_ids)} "
                f"both at day {day} period {period}"
            )
    return errors


def free_periods(instance, closed, resource):
    slots = len(instance.grid.days) * len(instance.grid.periods)
    free = slots - len(closed.get(resource.id, ()))
    if resource.max_load is not None:
        free = min(free, resource.max_load)
    return free


def load_errors(instance):
    resource_map = instance.resource_map
    closed = closed_slots(instance)
    needed = defaultdict(int)
    for requirement in instance.requirements:
        periods = requirement.sessions * requirement.length
        for person in participants(requirement):
            needed[person] += periods
    errors = []
    for resource in instance.resources:
        if resource.kind == ROOM:
            continue
        own = needed.get(resource.id, 0)
        inherited = needed.get(resource.parent, 0) if resource.kind == BATCH else 0
        total = own + inherited
        free = free_periods(instance, closed, resource)
        if total > free:
            detail = f" (including {inherited} of {resource.parent})" if inherited else ""
            errors.append(
                f"{resource.kind.title()} {resource.id} needs {total} periods{detail} "
                f"but has {free} free"
            )
    for requirement in instance.requirements:
        for person in participants(requirement):
            resource = resource_map.get(person)
            if resource is None:
                continue
            open_count = sum(
                1
                for day in range(len(instance.grid.days))
                for start in instance.grid.starts_for(requirement.length)
                if all(
                    (day, period) not in closed.get(person, ())
                    for period in covered_periods(start, requirement.length)
                )
            )
            if open_count == 0 and instance.grid.starts_for(requirement.length):
                errors.append(
                    f"{person} has no free slot of length {requirement.length} "
                    f"for requirement {requirement.id}"
                )
    return errors


def room_errors(instance):
    resource_map = instance.resource_map
    closed = closed_slots(instance)
    errors = []
    demands = []
    for requirement in instance.requirements:
        for position in range(room_positions(requirement)):
            needed = capacity_needed(resource_map, requirement, position)
            candidates = candidate_rooms(instance, requirement, position, resource_map)
            count = rooms_at_position(requirement, position)
            if len(candidates) < count:
                errors.append(
                    f"Requirement {requirement.id} needs {count} x "
                    f"{describe_rooms(requirement, needed)} but only {len(candidates)} exist"
                )
            demands.append(
                (requirement.room_tag, needed, requirement.sessions * requirement.length * count)
            )
            if splits_rooms(requirement):
                fixed = requirement.fixed_rooms[position : position + 1]
            else:
                fixed = requirement.fixed_rooms
            for room in fixed:
                if room in resource_map and room not in candidates:
                    errors.append(
                        f"Fixed room {room} for requirement {requirement.id} is not "
                        f"{describe_rooms(requirement, needed)}"
                    )
        if splits_rooms(requirement):
            distinct = set()
            for position in range(room_positions(requirement)):
                distinct.update(candidate_rooms(instance, requirement, position, resource_map))
            if len(distinct) < requirement.rooms_needed:
                errors.append(
                    f"Requirement {requirement.id} needs {requirement.rooms_needed} distinct "
                    f"rooms but only {len(distinct)} qualify"
                )
    rooms = [resource for resource in instance.resources if resource.kind == ROOM]
    for tag in dict.fromkeys(tag for tag, _needed, _periods in demands):
        thresholds = {needed for demand_tag, needed, _periods in demands if demand_tag == tag}
        for threshold in sorted(thresholds):
            demanded = sum(
                periods
                for demand_tag, needed, periods in demands
                if (tag is None or demand_tag == tag) and needed >= threshold
            )
            supply = sum(
                free_periods(instance, closed, room)
                for room in rooms
                if (tag is None or tag in room.tags) and room.capacity >= threshold
            )
            if demanded > supply:
                label = f"Rooms tagged {tag}" if tag else "Rooms"
                errors.append(
                    f"{label} with capacity >= {threshold} are needed for {demanded} "
                    f"periods but only {supply} are free"
                )
    return errors


def precheck(instance):
    errors = reference_errors(instance) + hierarchy_errors(instance)
    if errors:
        return errors
    return (
        grid_errors(instance)
        + fixed_collision_errors(instance)
        + load_errors(instance)
        + room_errors(instance)
    )
