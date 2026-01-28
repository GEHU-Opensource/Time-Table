"""
Constants for the timetable generation algorithm.
"""


class Defaults:
    """Default configuration values."""
    def __init__(self, config=None):
        config = config or {}
        self.room_capacity = config.get('room_capacity', 60)
        self.working_days = config.get('working_days', [
            "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"
        ])
        self.starting_section_fitness = config.get('starting_section_fitness', 1000)
        self.max_class_capacity = config.get('max_class_capacity', 250)
        self.initial_no_of_chromosomes = config.get('initial_no_of_chromosomes', 10)
        self.total_no_of_generations = config.get('total_no_of_generations', 50)
        self.class_strength = config.get('class_strength', 50)


class PenaltyConstants:
    """Penalty values for constraint violations."""
    def __init__(self, config=None):
        config = config or {}
        self.PENALTY_TEACHER_DOUBLE_BOOKED = config.get('teacher_double_booked', 30)
        self.PENALTY_CLASSROOM_DOUBLE_BOOKED = config.get('classroom_double_booked', 20)
        self.PENALTY_OVER_CAPACITY = config.get('over_capacity', 25)
        self.PENALTY_UN_PREFERRED_SLOT = config.get('un_preferred_slot', 5)
        self.PENALTY_OVERLOAD_TEACHER = config.get('overload_teacher', 10)
        self.PENALTY_NON_DUTY_DAY = config.get('non_duty_day', 40)
