from flask import Flask, request, jsonify

from GA import run_timetable_generation
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route("/generate", methods=["POST"])
def generate_timetable():
    data = request.get_json()

    # required inputs
    teacher_subject_mapping = data.get("teacher_subject_mapping", {})
    total_sections = data.get("total_sections", {})
    total_classrooms = data.get("total_classrooms", {})
    total_labs = data.get("total_labs", {})
    teacher_preferences = data.get("teacher_preferences", {})
    teacher_weekly_workload = data.get("teacher_weekly_workload", {})
    special_subjects = data.get("special_subjects", {})
    labs = data.get("labs", {})
    subject_quota_limits = data.get("subject_quota_limits", {})
    teacher_duty_days = data.get("teacher_duty_days", {})
    teacher_availability_matrix = data.get("teacher_availability_matrix", {})
    lab_availability_matrix = data.get("lab_availability_matrix", {})
    total_generations = data.get("total_generations", 50)
    time_slots = {int(k): v for k, v in data.get("time_slots", {}).items()}
    day_map = {str(k): int(v) for k, v in data.get("day_map", {}).items()}
    time_slot_map = {str(k): int(v) for k, v in data.get("time_slot_map", {}).items()}
    fixed_teacher_assignment = data.get("fixed_teacher_assignment", {})

    # run engine
    best_tt, final_teacher, final_lab = run_timetable_generation(
        teacher_subject_mapping,
        total_sections,
        total_classrooms,
        total_labs,
        teacher_preferences,
        teacher_weekly_workload,
        special_subjects,
        labs,
        subject_quota_limits,
        teacher_duty_days,
        teacher_availability_matrix,
        lab_availability_matrix,
        total_generations,
        time_slots,
        day_map,
        time_slot_map,
        fixed_teacher_assignment,
    )

    return jsonify({
        "timetable": best_tt,
        "teacher_availability": final_teacher,
        "lab_availability": final_lab
    })


if __name__ == "__main__":
    app.run(debug=True)