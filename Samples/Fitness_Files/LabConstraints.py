import json
import random

from constants.time_intervals import TimeIntervalConstant


class LabConstraintsConfig:
    def __init__(self, config=None):
        config = config or {}
        
        # Labs and Classes
        self.LABS = config.get('labs', ["Lab1", "Lab2", "Lab3", "Lab4"])
        self.CLASSES = config.get('classes', ["Class1", "Class2", "Class3", "Class4"])
        self.TEACHERS = config.get('teachers', ["Teacher1", "Teacher2", "Teacher3", "Teacher4"])
        
        # Constraints
        self.MAX_LAB_COUNT = config.get('max_lab_count', 2)  # Max labs per week for a teacher
        self.MAX_CLASS_COUNT = config.get('max_class_count', 3)  # Max classes per week for a teacher
        self.MAX_TEACHER_WORKLOAD = config.get('max_teacher_workload', 5)  # Max hours a teacher can work in a week
        self.MAX_CONTINUOUS_CLASSES = config.get('max_continuous_classes', 2)  # Max consecutive hours for a teacher
        
        # Workload for subjects
        self.SUBJECT_WORKLOAD = config.get('subject_workload', {
            "TCS-531": 3,
            "TCS-502": 3,
            "TCS-503": 3,
            "PCS-506": 1,
            "PCS-503": 1,
            "TMA-502": 3,
            "PMA-502": 1,
            "TCS-509": 3,
            "XCS-501": 2,
            "CSP-501": 1,
            "SCS-501": 1,
            "Placement_Class": 1,
        })
        
        # Teacher availability and subjects they teach
        self.TEACHER_SUBJECTS = config.get('teacher_subjects', {
            "TCS-531": ["AB01", "PK02"],
            "TCS-502": ["SS03", "AA04", "AC05"],
            "TCS-503": ["SP06", "DP07", "AC05"],
            "PCS-506": ["AD08", "RD09"],
            "TMA-502": ["BJ10", "RS11", "JM12", "NJ13"],
            "PMA-502": ["PM14", "AD08", "AA15"],
            "TCS-509": ["SJ16", "AB17", "HP18", "SG19"],
            "XCS-501": ["DT20", "PA21", "NB22"],
            "CSP-501": ["AK23"],
            "SCS-501": ["AP24"],
            "PCS-503": ["RS11", "DP07", "SP06", "VD25"],
            "Placement_Class": ["AK26"],
        })

# Initialize available time slots
TimeSlots = TimeIntervalConstant.time_slots


class TimetableFitness:
    def __init__(self, config=None):
        self.config = LabConstraintsConfig(config)
        self.teacher_schedule = {}

    def TeacherWorkload(self):
        """
        Ensure total workload per teacher is within the limit.
        """
        for teacher, schedule in self.teacher_schedule.items():
            total_hours = sum(
                self.config.SUBJECT_WORKLOAD.get(subject, 0) for subject in schedule.values()
            )
            if total_hours > self.config.MAX_TEACHER_WORKLOAD:
                return False
        return True

    def ContinuousClasses(self):
        """
        Ensure teachers do not have more than the allowed continuous classes.
        """
        for teacher, schedule in self.teacher_schedule.items():
            sorted_slots = sorted(schedule.keys())
            continuous_count = 0
            for i in range(len(sorted_slots) - 1):
                if (
                    TimeSlots.index(sorted_slots[i + 1])
                    - TimeSlots.index(sorted_slots[i])
                    == 1
                ):
                    continuous_count += 1
                    if continuous_count > self.config.MAX_CONTINUOUS_CLASSES:
                        return False
                else:
                    continuous_count = 0
        return True

    def fitnessFunc(self):
        """
        Calculate fitness score based on all constraints.
        """
        fitness_score = 0

        if self.LabNo():
            fitness_score += 10
        else:
            fitness_score -= 10

        if self.ClassNo():
            fitness_score += 10
        else:
            fitness_score -= 10

        if self.TeacherWorkload():
            fitness_score += 10
        else:
            fitness_score -= 10

        if self.ContinuousClasses():
            fitness_score += 10
        else:
            fitness_score -= 10

        return fitness_score


# Main Execution
timetable_fitness = TimetableFitness()

# Assign classes and labs to teachers
timetable_fitness.assign_classes_and_labs()

# Calculate fitness score
fitness_score = timetable_fitness.fitnessFunc()

# Output
print(f"Final Fitness Score: {fitness_score}")

# Save results to a JSON file
output = {
    "teacher_schedule": timetable_fitness.teacher_schedule,
    "fitness_score": fitness_score,
    "section_strength": timetable_fitness.section_strength,
}
with open("Timetable_Fitness_Result.json", "w") as f:
    json.dump(output, f, indent=4)
