from dataclasses import dataclass, field

DEFAULT_GRID = {
    "days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
    "periods": [
        ["09:00", "10:00"],
        ["10:00", "11:00"],
        ["11:00", "12:00"],
        ["12:00", "13:00"],
        ["14:00", "15:00"],
        ["15:00", "16:00"],
        ["16:00", "17:00"],
        ["17:00", "18:00"],
    ],
    "breaks_after": [3],
}

TEACHER = "teacher"
ROOM = "room"
ATTENDEE_KINDS = frozenset({"section", "batch"})


@dataclass(frozen=True)
class Entry:
    subject: str
    teachers: str
    rooms: str
    attendees: str


@dataclass
class Cell:
    day: int
    period: int
    entries: list = field(default_factory=list)
    changed: bool = False

    @property
    def css(self):
        return "slot changed" if self.changed else "slot"


@dataclass
class Row:
    day: str
    cells: list


@dataclass
class GridView:
    days: list
    periods: list
    rows: list

    @property
    def empty(self):
        return not any(cell.entries for row in self.rows for cell in row.cells)


@dataclass
class SlotCell:
    day: int
    period: int
    checked: bool

    @property
    def value(self):
        return f"{self.day}-{self.period}"


@dataclass
class SlotRow:
    day: str
    cells: list


def period_labels(grid):
    return [f"{start}-{end}" for start, end in grid["periods"]]


def empty_grid(grid):
    labels = period_labels(grid)
    rows = [
        Row(day=name, cells=[Cell(day=d, period=p) for p in range(len(labels))])
        for d, name in enumerate(grid["days"])
    ]
    return GridView(days=list(grid["days"]), periods=labels, rows=rows)


def codes(members, predicate):
    return ", ".join(
        sorted({m["resource__code"] for m in members if predicate(m["resource__kind"])})
    )


def entry_for(members):
    return Entry(
        subject=members[0]["requirement__subject__code"],
        teachers=codes(members, lambda kind: kind == TEACHER),
        rooms=codes(members, lambda kind: kind == ROOM),
        attendees=codes(members, lambda kind: kind in ATTENDEE_KINDS),
    )


def group_sessions(rows):
    groups = {}
    for row in rows:
        key = (row["requirement_id"], row["session"], row["day"], row["period"])
        groups.setdefault(key, []).append(row)
    return groups


def involves(member, resource_id):
    return resource_id in {member["resource_id"], member.get("resource__parent_id")}


def build_grid(grid, rows, resource_id):
    view = empty_grid(grid)
    for (_, _, day, period), members in group_sessions(rows).items():
        if not any(involves(m, resource_id) for m in members):
            continue
        if day >= len(view.rows) or period >= len(view.periods):
            continue
        view.rows[day].cells[period].entries.append(entry_for(members))
    for row in view.rows:
        for cell in row.cells:
            cell.entries.sort(key=lambda entry: entry.subject)
    return view


def mark_changes(left, right):
    for day in range(max(len(left.rows), len(right.rows))):
        for period in range(max(len(left.periods), len(right.periods))):
            a = cell_at(left, day, period)
            b = cell_at(right, day, period)
            a_entries = set(a.entries) if a else set()
            b_entries = set(b.entries) if b else set()
            if a_entries == b_entries:
                continue
            if a:
                a.changed = True
            if b:
                b.changed = True
    return left, right


def cell_at(view, day, period):
    if day < len(view.rows) and period < len(view.rows[day].cells):
        return view.rows[day].cells[period]
    return None


def slot_choices(grid):
    return [
        (f"{d}-{p}", f"{day} {p + 1}")
        for d, day in enumerate(grid["days"])
        for p in range(len(grid["periods"]))
    ]


def parse_slot(value):
    day, period = str(value).split("-")
    return [int(day), int(period)]


def slot_values(slots):
    return [f"{day}-{period}" for day, period in slots]


def slot_rows(grid, selected):
    chosen = {(int(day), int(period)) for day, period in (parse_slot(v) for v in selected)}
    return [
        SlotRow(
            day=name,
            cells=[
                SlotCell(day=d, period=p, checked=(d, p) in chosen)
                for p in range(len(grid["periods"]))
            ],
        )
        for d, name in enumerate(grid["days"])
    ]


def day_index(token, days):
    wanted = token.strip().lower()
    for index, name in enumerate(days):
        if name.lower() == wanted or name.lower().startswith(wanted[:3]):
            return index
    raise ValueError(f"unknown day '{token.strip()}'")


def parse_fixed_slots(text, grid):
    slots = []
    for piece in (part.strip() for part in text.replace(";", ",").split(",")):
        if not piece:
            continue
        parts = piece.split()
        if len(parts) != 2 or not parts[1].isdigit():
            raise ValueError(f"'{piece}' is not of the form 'Mon 1'")
        day = day_index(parts[0], grid["days"])
        period = int(parts[1])
        if not 1 <= period <= len(grid["periods"]):
            raise ValueError(f"period {period} is outside 1-{len(grid['periods'])}")
        slot = [day, period - 1]
        if slot not in slots:
            slots.append(slot)
    return slots


def format_fixed_slots(slots, grid):
    days = grid["days"]
    return ", ".join(f"{days[day]} {start + 1}" for day, start in slots if 0 <= day < len(days))
