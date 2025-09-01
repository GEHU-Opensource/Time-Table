class Defaults:
    def __init__(self, config=None):
        config = config or {}
        self.room_capacity = config.get('room_capacity', 60)
        self.working_days = config.get('working_days', ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"])
        self.starting_section_fitness = config.get('starting_section_fitness', 1000)
        self.max_class_capacity = config.get('max_class_capacity', 250)
        self.initial_no_of_chromosomes = config.get('initial_no_of_chromosomes', 1000)
        self.total_no_of_generations = config.get('total_no_of_generations', 100)
        self.class_strength = config.get('class_strength', 50)



class TeacherPreferences:
    def __init__(self, teacher_weekly_workload: dict):
        self.teacher_preferences = {}
        for teacher, workload in teacher_weekly_workload.items():
            self.teacher_preferences[teacher] = list(range(1, 8))

    def get_preferences(self):
        return self.teacher_preferences


class SubjectWeeklyQuota:
    def __init__(self, subject_quota):
        self.subject_quota = subject_quota


class TeacherPreloads:
    def __init__(self, teacher_preferences: dict, weekly_workload: dict):
        self.teacher_preferences = teacher_preferences
        self.weekly_workload = weekly_workload


class TeachersDutyDays:
    def __init__(self, teacher_duty_days: dict):
        self.teacher_duty_days = teacher_duty_days


class SpecialSubjects:
    def __init__(
        self, special_subjects: list, labs: list, specialization_subjects: list
    ):
        self.special_subjects = special_subjects
        self.labs = labs
        self.specialization_subjects = specialization_subjects


class PenaltyConstants:
    def __init__(self, config=None):
        config = config or {}
        self.PENALTY_TEACHER_DOUBLE_BOOKED = config.get('teacher_double_booked', 30)
        self.PENALTY_CLASSROOM_DOUBLE_BOOKED = config.get('classroom_double_booked', 20)
        self.PENALTY_OVER_CAPACITY = config.get('over_capacity', 25)
        self.PENALTY_UN_PREFERRED_SLOT = config.get('un_preferred_slot', 5)
        self.PENALTY_OVERLOAD_TEACHER = config.get('overload_teacher', 10)
        self.PENALTY_NON_DUTY_DAY = config.get('non_duty_day', 40)


class SectionsConstants:
    # Define attribute weights and conditions
    ATTRIBUTE_WEIGHTS = {
        'good_cgpa': 1,         # 2^0
        'hostler': 2,           # 2^1
    }

    ATTRIBUTE_CONDITIONS = {
        'hostler': lambda student: student.get('Hostler', False),
    }
    
    # Add class-level attributes to Defaults for backward compatibility
    Defaults.working_days = Defaults().working_daysD
    Defaults.max_class_capacity = Defaults().max_class_capacity
    Defaults.initial_no_of_chromosomes = Defaults().initial_no_of_chromosomes
    Defaults.total_no_of_generations = Defaults().total_no_of_generations

