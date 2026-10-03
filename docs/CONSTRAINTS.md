# Constraint rules

Every hard rule is enforced at least twice: once inside the CP-SAT model (so no violating
solution can leave the solver) and once in the independent validator (`solver/validate`),
which re-reads the placements and rejects anything the model should have prevented. Where the
database can state the rule, a constraint or trigger enforces it a third time at write time.
Soft rules are objective terms only.

Slot vocabulary: a `Grid` has days and periods; breaks split the periods of a day into blocks
(`Grid.blocks`). A requirement of `length` L occupies L consecutive periods inside one block.
Each occupied period produces one `Assignment` row per participating resource (teacher, every
room, section or batch), so an occupancy row is the unit of all double-booking checks.

| # | Rule | Kind | Solver | Validator | Database | Service / UI |
|---|---|---|---|---|---|---|
| 1 | A teacher is in at most one session per period. | hard | `AddAtMostOne` over the teacher's candidate literals per slot | counts rows per (teacher, day, period) | `assignment_slot_unique (version, resource, day, period)`; live rows: `assignment_live_slot_unique` | |
| 2 | A room hosts at most one session per period. | hard | at-most-one per (room, slot) | same count per room | same unique indexes | |
| 3 | A section attends at most one session per period. | hard | at-most-one per (section, slot) | same count per section | same unique indexes | |
| 4 | A batch attends at most one session per period. | hard | at-most-one per (batch, slot) | same count per batch | same unique indexes | |
| 5 | Batch-parent exclusivity: a batch is busy whenever its parent section is, and the section is busy whenever any of its batches is. | hard | the section's at-most-one group includes every literal that occupies one of its batches, and each batch group includes the section's literals | expands batch rows to the parent and parent rows to the batches before counting | batch rows carry `serves = parent section`; `resource_batch_has_parent` check guarantees a parent exists | `build_instance` sets `Resource.parent` |
| 6 | Room capacity: the room's capacity is at least the attendee head count. | hard | candidate rooms filtered before literals are created | recomputes head count per placement | `resource_room_has_capacity` (capacity > 0) | |
| 7 | Room tags: a requirement with `room_tag` only uses rooms that carry the tag. | hard | candidate rooms filtered | checks tag membership | | import rejects unknown tags |
| 8 | Rooms needed: exactly `rooms_needed` distinct rooms per session. | hard | one room literal set per session with `Add(sum == rooms_needed)` | counts distinct rooms | `requirement_rooms (rooms_needed <= 8)` | |
| 9 | Exact weekly sessions: each requirement is placed exactly `sessions` times. | hard | `AddExactlyOne` per (requirement, session index) | counts placements per requirement | `requirement_sessions (sessions >= 1)` | unplaced sessions mark the solve `failed` |
| 10 | Sessions per day: at most one session of a requirement per day (two when `sessions` exceeds the number of days). | hard | at-most-k over the requirement's literals on a day | counts per (requirement, day) | | |
| 11 | A session of length L lies inside one block and does not cross a break. | hard | start literals only for `Grid.starts_for(L)` | checks `block_of(start) == block_of(start + L - 1)` | `subject_length`, `requirement_length` (1-4) | grid editor refuses blocks shorter than the longest length |
| 12 | Teacher max load: a teacher's occupied periods per week do not exceed `max_load`. | hard | `Add(sum(periods) <= max_load)` | sums rows per teacher | `resource_teacher_has_max_load` (max_load not null) | |
| 13 | Unavailable slots: a resource is never used in a slot listed in `unavailable`. | hard | literals for those slots are not created | checks membership | | editable per resource |
| 14 | Blocked by other live timetables: a resource with a live assignment in another timetable is unavailable in that slot. | hard | `Instance.blocked` removes the literals | checks against `blocked` | `assignment_live_slot_unique` across the whole tenant at `flip_live` time | `blocked_slots(version)` reads live rows; `publish` re-validates against them under the advisory lock |
| 15 | Fixed rooms: a requirement with `fixed_room` participants uses exactly those rooms. | hard | room candidates are only the fixed rooms | checks equality | `requirement_resource_unique` | |
| 16 | Fixed slots: a requirement with `fixed_slots` places its sessions exactly there. | hard | `Add(literal == 1)` for the fixed start | checks placement | | validated against the grid on save |
| 17 | Gaps: minimise idle periods between a section's first and last session of a day. | soft | linear penalty on span minus occupied periods | not checked | | shown in `solver_stats` |
| 18 | Teacher gaps: minimise idle periods for teachers within a day. | soft | same shape, lower weight | not checked | | |
| 19 | Preferred slots: reward placing a resource in its `preferred` slots. | soft | bonus per satisfied preference | not checked | | editable per resource |
| 20 | Spread: prefer sessions of one requirement on distinct, spaced days. | soft | penalty on adjacent-day pairs | not checked | | |
| 21 | Minimal change on re-solve: keep placements of the parent version where possible. | soft | parent placements as `Instance.hints` plus a penalty per moved session | `compare(parent, child)` reports moved sessions | | the diff view highlights changed cells |
| 22 | Determinism: identical instance and `seed` produce identical output. | process | `random_seed = Instance.seed`, fixed worker count | | | `seed` stored in `solver_stats` |
| 23 | Size and time: model within `SOLVER_MAX_MODEL_SIZE`, wall clock within `SOLVER_MAX_SECONDS`, memory within `SOLVER_MEMORY_BYTES`. | process | `max_time_in_seconds`; literal count checked before solving, returns `too_large` | | | sandbox subprocess with `RLIMIT_AS`; rate limit `SOLVES_PER_TENANT_PER_HOUR` |

## Reading the table

- "Solver" names the CP-SAT construct used in `solver/model`.
- "Validator" names the independent check in `solver/validate`; it uses only the
  `Instance` and the placements, never the model, so a modelling bug cannot hide a clash.
- "Database" names the constraint, index or trigger from `timetable/models.py` and the
  `0002_security` migrations.
- "Service / UI" names the surrounding guard in `timetable/services.py` or the forms.

A solve result whose validator report is not empty is stored as `failed` with the violations in
`solver_stats.violations`; its placements are never written as assignments.
