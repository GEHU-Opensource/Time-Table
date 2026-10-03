from solver.types import Placement


def solve_instance(instance):
    from solver.model import solve

    return solve(instance)


def validate_placements(instance, placements):
    from solver.validate import validate

    return list(validate(instance, tuple(placements)))


def precheck_instance(instance):
    from solver.precheck import precheck

    return list(precheck(instance))


def explain_instance(instance):
    from solver.explain import explain

    return explain(instance)


def serves_each_attendee(requirement, rooms):
    return requirement.rooms_needed == len(requirement.attendees) > 1 and len(rooms) == len(
        requirement.attendees
    )


def occupancy_rows(instance, placements):
    rows = []
    requirements = instance.requirement_map
    for placement in placements:
        requirement = requirements[placement.requirement]
        per_attendee = serves_each_attendee(requirement, placement.rooms)
        for period in range(placement.start, placement.start + requirement.length):
            for teacher in requirement.teachers:
                rows.append(
                    (placement.requirement, placement.session, teacher, placement.day, period, None)
                )
            for attendee in requirement.attendees:
                rows.append(
                    (
                        placement.requirement,
                        placement.session,
                        attendee,
                        placement.day,
                        period,
                        None,
                    )
                )
            for index, room in enumerate(placement.rooms):
                serves = requirement.attendees[index] if per_attendee else None
                rows.append(
                    (placement.requirement, placement.session, room, placement.day, period, serves)
                )
    return rows


def placements_from_rows(rows, room_ids, attendee_positions):
    groups = {}
    for requirement_id, session, resource_id, day, period, serves_id in rows:
        group = groups.setdefault(
            (requirement_id, session), {"day": day, "periods": set(), "rooms": {}}
        )
        group["periods"].add(period)
        if resource_id in room_ids:
            group["rooms"][resource_id] = serves_id
    placements = []
    for (requirement_id, session), group in groups.items():
        positions = attendee_positions.get(requirement_id, {})
        rooms = group["rooms"]
        ordered = tuple(
            sorted(rooms, key=lambda room: (positions.get(rooms[room], len(positions)), room))
        )
        placements.append(
            Placement(
                requirement=requirement_id,
                session=session,
                day=group["day"],
                start=min(group["periods"]),
                rooms=ordered,
            )
        )
    return tuple(
        sorted(placements, key=lambda placement: (placement.requirement, placement.session))
    )
