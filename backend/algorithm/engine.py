"""
Timetable generation engine using Genetic Algorithm.
"""
import copy
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

from algorithm.chromosome import TimeTableGeneration
from algorithm.fitness import TimetableFitnessEvaluator
from algorithm.mutation import TimeTableCrossOver, TimeTableMutation
from algorithm.selection import TimeTableSelection
from algorithm.helpers import (
    initialize_teacher_availability,
    update_matrix_for_best,
    update_teacher_availability_matrix,
)
from algorithm.constants import Defaults


@dataclass
class TimetableConfig:
    """Configuration for timetable generation."""
    teacher_subject_mapping: dict
    total_sections: dict
    total_classrooms: dict
    total_labs: dict
    teacher_preferences: dict
    teacher_weekly_workload: dict
    special_subjects: dict
    labs: dict
    subject_quota_limits: dict
    teacher_duty_days: dict
    teacher_availability_matrix: dict
    lab_availability_matrix: dict
    total_generations: int
    time_slots: dict
    day_map: dict
    time_slot_map: dict
    prev_selected: dict = None
    prev_mutated: list = None
    fixed_teacher_assignment: dict = None
    working_days: list = None


class TimetableEngine:
    """Main engine for generating timetables using Genetic Algorithm."""
    
    def __init__(self, config: TimetableConfig):
        self.config = config
        self.teacher_availability = copy.deepcopy(config.teacher_availability_matrix)
        self.lab_availability = copy.deepcopy(config.lab_availability_matrix)
        
        # Set working days
        if config.working_days:
            from algorithm.constants import Defaults
            defaults = Defaults({'working_days': config.working_days})
            self.working_days = defaults.working_days
        else:
            defaults = Defaults()
            self.working_days = defaults.working_days

    def _update_lab_availability(self, best_timetable):
        """Update lab availability based on best timetable."""
        updated_lab = copy.deepcopy(self.config.lab_availability_matrix)
        for weekday, daily_schedule in best_timetable.items():
            day_index = self.config.day_map.get(weekday)
            if day_index is None:
                continue
            for allocations in daily_schedule.values():
                for alloc in allocations:
                    lab = alloc.get("classroom_id")
                    ts_index = self.config.time_slot_map.get(alloc.get("time_slot"))
                    if lab in updated_lab and ts_index is not None:
                        if (day_index < len(updated_lab[lab]) and 
                            ts_index - 1 < len(updated_lab[lab][day_index])):
                            updated_lab[lab][day_index][ts_index - 1] = False
        return updated_lab

    def _generate_timetable(self, teacher_matrix):
        """Generate a single generation of timetables."""
        tg = TimeTableGeneration(
            teacher_subject_mapping=self.config.teacher_subject_mapping,
            total_sections=self.config.total_sections,
            total_classrooms=self.config.total_classrooms,
            total_labs=self.config.total_labs,
            teacher_preferences=self.config.teacher_preferences,
            teacher_weekly_workload=self.config.teacher_weekly_workload,
            special_subjects=self.config.special_subjects,
            labs=self.config.labs,
            subject_quota_limits=self.config.subject_quota_limits,
            teacher_duty_days=self.config.teacher_duty_days,
            teacher_availability_matrix=teacher_matrix,
            lab_availability_matrix=self.lab_availability,
            time_slots=self.config.time_slots,
            fixed_teacher_assignment=self.config.fixed_teacher_assignment or {}
        )

        # Generate multiple weeks (chromosomes)
        num_weeks = self.config.total_generations if self.config.total_generations < 10 else 10
        timetable, updated_teacher, _ = tg.create_timetable(num_weeks)

        # Evaluate fitness
        fitness = TimetableFitnessEvaluator(
            timetable=timetable,
            all_sections=list(tg.sections_manager.keys()),
            subject_teacher_mapping=tg.subject_teacher_mapping,
            available_classrooms=list(tg.classrooms_manager.keys()),
            available_labs=list(tg.lab_capacity_manager.keys()),
            classroom_capacity=tg.classrooms_manager,
            section_student_strength=tg.sections_manager,
            subject_quota_data=tg.subject_quota_limits,
            teacher_time_preferences=tg.teacher_availability_preferences,
            teacher_daily_workload=tg.weekly_workload,
            time_slots=self.config.time_slots,
        ).evaluate_timetable_fitness()

        # Selection
        selected = TimeTableSelection().select_chromosomes(fitness[1])
        if self.config.prev_selected:
            selected.update(self.config.prev_selected)

        # Crossover
        crossover = TimeTableCrossOver()
        crossover_chromosomes = []
        selected_keys = list(selected.keys())
        for i in range(0, len(selected_keys), 2):
            if i + 1 < len(selected_keys):
                c1, c2 = crossover.perform_crossover(
                    timetable[selected_keys[i]], timetable[selected_keys[i + 1]]
                )
                crossover_chromosomes.extend([c1, c2])

        # Mutation
        mutated = [TimeTableMutation().mutate_schedule_for_week(ch) for ch in crossover_chromosomes]
        if self.config.prev_mutated:
            mutated.extend(self.config.prev_mutated)

        # Find best chromosome
        best_chromosome, best_score = None, -1
        for key, score in selected.items():
            score = int(score)
            if score > best_score and key in timetable:
                best_score = score
                best_chromosome = timetable[key]

        if best_chromosome:
            updated_teacher = update_teacher_availability_matrix(teacher_matrix, best_chromosome)
        
        return best_chromosome, updated_teacher, selected, mutated, best_score

    def run(self):
        """Run the genetic algorithm to generate optimal timetable."""
        initial_teacher = copy.deepcopy(self.teacher_availability)
        updated_teacher = copy.deepcopy(initial_teacher)
        best_chromosome = None
        best_score = -1

        self.config.prev_selected = None
        self.config.prev_mutated = None

        # Run for specified number of generations
        for generation in range(self.config.total_generations):
            teacher_copy = copy.deepcopy(initial_teacher)
            best, updated_teacher, selected, mutated, score = self._generate_timetable(teacher_copy)
            
            if best and score > best_score:
                best_chromosome = best
                best_score = score

            self.config.prev_selected = selected
            self.config.prev_mutated = mutated

        # Update teacher availability for final best timetable
        if best_chromosome:
            updated_teacher = update_matrix_for_best(
                best_chromosome,
                updated_teacher,
                self.config.day_map,
                self.config.time_slot_map,
            )

        updated_lab = self._update_lab_availability(best_chromosome) if best_chromosome else self.lab_availability
        
        return best_chromosome, updated_teacher, updated_lab, best_score


def run_timetable_generation(
    teacher_subject_mapping: dict,
    total_sections: dict,
    total_classrooms: dict,
    total_labs: dict,
    teacher_preferences: dict,
    teacher_weekly_workload: dict,
    special_subjects: dict,
    labs: dict,
    subject_quota_limits: dict,
    teacher_duty_days: dict,
    teacher_availability_matrix: dict,
    lab_availability_matrix: dict,
    total_generations: int,
    time_slots: dict,
    day_map: dict,
    time_slot_map: dict,
    fixed_teacher_assignment: dict = None,
    working_days: list = None,
):
    """Main function to run timetable generation."""
    config = TimetableConfig(
        teacher_subject_mapping=teacher_subject_mapping,
        total_sections=total_sections,
        total_classrooms=total_classrooms,
        total_labs=total_labs,
        teacher_preferences=teacher_preferences,
        teacher_weekly_workload=teacher_weekly_workload,
        special_subjects=special_subjects,
        labs=labs,
        subject_quota_limits=subject_quota_limits,
        teacher_duty_days=teacher_duty_days,
        teacher_availability_matrix=teacher_availability_matrix,
        lab_availability_matrix=lab_availability_matrix,
        total_generations=total_generations,
        time_slots=time_slots,
        day_map=day_map,
        time_slot_map=time_slot_map,
        fixed_teacher_assignment=fixed_teacher_assignment or {},
        working_days=working_days,
    )
    engine = TimetableEngine(config)
    return engine.run()
