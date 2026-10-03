import json
from pathlib import Path

from hypothesis import strategies as st

from solver.types import (
    BATCH,
    ROOM,
    SECTION,
    TEACHER,
    Grid,
    Instance,
    Placement,
    Requirement,
    Resource,
)

FIXTURES = Path(__file__).parent / "fixtures"

PERIODS = (
    ("09:00", "09:55"),
    ("09:55", "10:50"),
    ("11:00", "11:55"),
    ("11:55", "12:50"),
    ("13:20", "14:15"),
    ("14:15", "15:10"),
    ("15:10", "16:05"),
    ("16:05", "17:00"),
)


def grid(days=5, periods=8, breaks_after=(1, 3)):
    return Grid(
        days=tuple(("Mon", "Tue", "Wed", "Thu", "Fri", "Sat")[:days]),
        periods=PERIODS[:periods],
        breaks_after=frozenset(index for index in breaks_after if index < periods - 1),
    )


def teacher(resource_id, **overrides):
    return Resource(resource_id, TEACHER, **overrides)


def room(resource_id, capacity=60, tags=("class",), **overrides):
    return Resource(resource_id, ROOM, capacity=capacity, tags=frozenset(tags), **overrides)


def section(resource_id, capacity=60, **overrides):
    return Resource(resource_id, SECTION, capacity=capacity, **overrides)


def batch(resource_id, parent, capacity=30, **overrides):
    return Resource(resource_id, BATCH, capacity=capacity, parent=parent, **overrides)


def requirement(requirement_id, teachers=("T1",), attendees=("S1",), length=1, sessions=1, **kw):
    kw.setdefault("room_tag", "class")
    return Requirement(
        requirement_id,
        kw.pop("subject", requirement_id),
        length,
        sessions,
        tuple(teachers),
        tuple(attendees),
        **kw,
    )


def instance(resources, requirements, **overrides):
    overrides.setdefault("max_seconds", 10.0)
    overrides.setdefault("workers", 4)
    return Instance(
        overrides.pop("grid", grid()), tuple(resources), tuple(requirements), **overrides
    )


def basic_resources():
    return (
        teacher("T1"),
        teacher("T2"),
        room("R1"),
        room("R2"),
        room("L1", capacity=30, tags=("lab",)),
        room("L2", capacity=30, tags=("lab",)),
        section("S1"),
        batch("G1", "S1"),
        batch("G2", "S1"),
    )


def placement_map(placements):
    return {(placement.requirement, placement.session): placement for placement in placements}


def resource_from_json(data):
    return Resource(
        id=data["id"],
        kind=data["kind"],
        capacity=data.get("capacity", 0),
        tags=frozenset(data.get("tags", [])),
        max_load=data.get("max_load"),
        unavailable=frozenset(tuple(slot) for slot in data.get("unavailable", [])),
        preferred=frozenset(tuple(slot) for slot in data.get("preferred", [])),
        parent=data.get("parent"),
    )


def requirement_from_json(data):
    return Requirement(
        id=data["id"],
        subject=data["subject"],
        length=data["length"],
        sessions=data["sessions"],
        teachers=tuple(data["teachers"]),
        attendees=tuple(data["attendees"]),
        rooms_needed=data.get("rooms_needed", 1),
        room_tag=data.get("room_tag"),
        fixed_rooms=tuple(data.get("fixed_rooms", [])),
        fixed_slots=tuple(tuple(slot) for slot in data.get("fixed_slots", [])),
    )


def instance_from_json(data):
    return Instance(
        grid=Grid.from_json(data["grid"]),
        resources=tuple(resource_from_json(item) for item in data["resources"]),
        requirements=tuple(requirement_from_json(item) for item in data["requirements"]),
        blocked=frozenset((rid, day, period) for rid, day, period in data.get("blocked", [])),
        hints=tuple(Placement(**hint) for hint in data.get("hints", [])),
        max_seconds=data.get("max_seconds", 120.0),
        workers=data.get("workers", 4),
        seed=data.get("seed", 0),
        max_model_size=data.get("max_model_size", 5_000_000),
    )


def load_fixture(name):
    with (FIXTURES / name).open() as handle:
        return instance_from_json(json.load(handle))


@st.composite
def small_instances(draw):
    days = draw(st.integers(min_value=2, max_value=5))
    periods = draw(st.integers(min_value=3, max_value=6))
    the_grid = grid(days, periods, breaks_after=(1,))
    teacher_count = draw(st.integers(min_value=1, max_value=4))
    room_count = draw(st.integers(min_value=1, max_value=3))
    section_count = draw(st.integers(min_value=1, max_value=2))
    teachers = []
    for index in range(teacher_count):
        unavailable = draw(
            st.frozensets(
                st.tuples(
                    st.integers(min_value=0, max_value=days - 1),
                    st.integers(min_value=0, max_value=periods - 1),
                ),
                max_size=3,
            )
        )
        preferred = draw(
            st.frozensets(
                st.tuples(
                    st.integers(min_value=0, max_value=days - 1),
                    st.integers(min_value=0, max_value=periods - 1),
                ),
                max_size=3,
            )
        )
        max_load = draw(st.one_of(st.none(), st.integers(min_value=2, max_value=12)))
        teachers.append(
            teacher(f"T{index}", unavailable=unavailable, preferred=preferred, max_load=max_load)
        )
    rooms = [
        room(
            f"R{index}",
            capacity=draw(st.sampled_from([30, 60, 90])),
            tags=draw(st.sampled_from([("class",), ("lab",), ("class", "lab")])),
        )
        for index in range(room_count)
    ]
    attendees = []
    sections = []
    for index in range(section_count):
        sections.append(section(f"S{index}"))
        batch_count = draw(st.integers(min_value=0, max_value=2))
        for sub in range(batch_count):
            attendees.append(batch(f"S{index}G{sub}", f"S{index}"))
    attendees = sections + attendees
    requirement_count = draw(st.integers(min_value=1, max_value=6))
    requirements = []
    for index in range(requirement_count):
        length = draw(st.integers(min_value=1, max_value=2))
        sessions = draw(st.integers(min_value=1, max_value=3))
        chosen_teachers = draw(
            st.lists(st.sampled_from([t.id for t in teachers]), min_size=1, max_size=2, unique=True)
        )
        chosen_attendees = draw(
            st.lists(
                st.sampled_from([a.id for a in attendees]), min_size=1, max_size=2, unique=True
            )
        )
        rooms_needed = draw(st.sampled_from([0, 1, len(chosen_attendees)]))
        room_tag = draw(st.sampled_from([None, "class", "lab"]))
        fixed_slots = ()
        if draw(st.booleans()):
            fixed_slots = (
                (
                    draw(st.integers(min_value=0, max_value=days - 1)),
                    draw(st.sampled_from(the_grid.starts_for(length))),
                ),
            )
        requirements.append(
            requirement(
                f"Q{index}",
                teachers=chosen_teachers,
                attendees=chosen_attendees,
                length=length,
                sessions=sessions,
                rooms_needed=rooms_needed,
                room_tag=room_tag,
                fixed_slots=fixed_slots,
            )
        )
    blocked = draw(
        st.frozensets(
            st.tuples(
                st.sampled_from([r.id for r in rooms + teachers]),
                st.integers(min_value=0, max_value=days - 1),
                st.integers(min_value=0, max_value=periods - 1),
            ),
            max_size=3,
        )
    )
    return instance(
        teachers + rooms + attendees,
        requirements,
        grid=the_grid,
        blocked=blocked,
        max_seconds=5.0,
        workers=2,
        seed=draw(st.integers(min_value=0, max_value=1000)),
    )
