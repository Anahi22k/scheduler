import json
import re
from flask import Flask, request, jsonify
from flask_cors import CORS

from requirement_engine import build_remaining_requirements
from recommendation_engine import rank_courses
from schedule_generator import (
    prepare_courses,
    generate_valid_schedules,
    rank_schedules,
    extract_credits,
    total_credits,
)

app = Flask(__name__)
CORS(app)

# =========================
# LOAD DATA
# =========================

# Load all course offerings
with open("data/courses_clean.json") as f:
    courses = json.load(f)

# Load career data (used for career-based recommendations)
with open("data/onet_careers.json") as f:
    careers = json.load(f)

# Load AU Core requirements
with open("data/programs/au_core.json") as f:
    au_core = json.load(f)

# Load ALL majors (generated from scraper)
# Each major contains: { "all_courses": [...] }
with open("data/programs/programs_all.json") as f:
    PROGRAMS = json.load(f)

# Preprocess course time data once at startup
prepared_courses = prepare_courses(courses)

# =========================
# HELPER FUNCTIONS
# =========================

def normalize_course_code(code):
    return (code or "").strip().upper()


def parse_prereq_text(course):
    description = course.get("description", "") or ""
    prereq = re.search(r"Prerequisite(?:/Concurrent)?:\s*(.*?)(?:\.|$)", description)
    return prereq.group(1).strip() if prereq else ""


def parse_restriction_text(course):
    description = course.get("description", "") or ""
    restriction = re.search(r"Restriction:\s*(.*?)(?:\.|$)", description)
    return restriction.group(1).strip() if restriction else ""


def eligibility_result(course, student):
    completed = set(student.get("completed_courses", []))
    prereq_text = parse_prereq_text(course)
    prereq_text_lower = prereq_text.lower()
    required_codes = re.findall(r"[A-Z]{3,4}-\d{3}", prereq_text.upper())
    has_explicit_prereq_data = bool(prereq_text.strip())

    if course["course"] in completed:
        return False, "already_completed"

    # Missing/unknown prerequisite data is treated as OPEN.
    # We only enforce prerequisites when explicit prerequisite text exists.
    if has_explicit_prereq_data and (
        "junior standing" in prereq_text_lower or "senior standing" in prereq_text_lower
    ):
        return False, "standing_requirement"

    if has_explicit_prereq_data and required_codes and "concurrent" not in prereq_text_lower:
        or_groups = re.split(r"\bor\b", prereq_text_lower)
        group_satisfied = False
        for group in or_groups:
            group_codes = re.findall(r"[A-Z]{3,4}-\d{3}", group.upper())
            if group_codes and all(code in completed for code in group_codes):
                group_satisfied = True
                break
        if not group_satisfied:
            return False, "missing_prerequisite"

    if has_explicit_prereq_data and "credit" in prereq_text_lower and "hour" in prereq_text_lower:
        credit_match = re.search(r"(\d+)", prereq_text_lower)
        if credit_match and student.get("credits_completed", 0) < int(credit_match.group(1)):
            return False, "insufficient_credits_completed"

    restriction_text = parse_restriction_text(course).lower()
    major = (student.get("major") or "").lower()
    if restriction_text and "not allowed" not in restriction_text and major and major not in restriction_text:
        return False, "major_restriction"

    return True, None


def schedule_ranking_details(schedule):
    required_count = sum(1 for c in schedule if c.get("ranking", {}).get("is_required"))
    career_alignment_score = round(
        sum(c.get("ranking", {}).get("career_similarity", 0.0) for c in schedule), 2
    )
    total_recommendation_score = round(
        sum(c.get("ranking", {}).get("score", 0.0) for c in schedule), 3
    )
    credits = round(total_credits(schedule), 2)
    workload_balance_penalty = round(abs(15.0 - credits), 2)
    explanation = (
        f"Ranked by degree progress first ({required_count} required courses), "
        f"then career alignment ({career_alignment_score}), "
        f"then workload balance (distance from 15 credits: {workload_balance_penalty}), "
        f"then overall recommendation score ({total_recommendation_score})."
    )

    return {
        "required_course_count": required_count,
        "career_alignment_score": career_alignment_score,
        "total_recommendation_score": total_recommendation_score,
        "workload_balance_penalty": workload_balance_penalty,
        "ranking_explanation": explanation,
    }
# =========================
# ROUTES
# =========================

@app.route("/careers")
def get_careers():
    """
    Returns a list of career titles for frontend autocomplete.
    """
    return jsonify([c["title"] for c in careers])


@app.route("/generate", methods=["POST"])
def generate():
    data = request.json or {}

    # Map frontend days to backend format.
    day_map = {
        "Mon": "M", "Monday": "M",
        "Tue": "T", "Tuesday": "T",
        "Wed": "W", "Wednesday": "W",
        "Thu": "R", "Thursday": "R",
        "Fri": "F", "Friday": "F",
        "Sat": "Sa", "Saturday": "Sa",
        "Sun": "Su", "Sunday": "Su"
    }

    unavailable_days = [
        day_map.get(d, d) for d in data.get("unavailable_days", [])
    ]

    # Build student profile
    student = {
        "major": data.get("major"),
        "completed_courses": data.get("completed_courses", []),
        "credits_completed": data.get("credits_completed", 0)
    }

    program = PROGRAMS.get(student["major"], {})
    interests = data.get("interests", "")
    career = data.get("career", "")
    max_courses = data.get("max_courses", 5)
    min_credits = float(data.get("min_credits", 12))
    max_credits = float(data.get("max_credits", 17))

    requirement_state = build_remaining_requirements(
        programs=PROGRAMS,
        au_core=au_core,
        major=student["major"],
        completed_courses=student["completed_courses"],
        all_courses=prepared_courses,
    )
    remaining_required = requirement_state["remaining_required_courses"]
    remaining_required_set = set(remaining_required)

    completed_set = {normalize_course_code(c) for c in student["completed_courses"]}
    eligible_courses = [
        c for c in prepared_courses
        if normalize_course_code(c.get("course")) not in completed_set
    ]

    ranked_courses = rank_courses(
        courses=eligible_courses,
        remaining_required_courses=remaining_required,
        career_text=career,
        interests_text=interests,
    )

    # Keep high-signal candidate pool for schedule search.
    candidate_courses = [
        c for c in ranked_courses
        if c["ranking"]["is_required"]
        or c["ranking"]["career_similarity"] >= 45
        or c["ranking"]["interest_similarity"] >= 40
    ]
    if not candidate_courses:
        candidate_courses = ranked_courses[:300]

    schedules, scheduler_diagnostics = generate_valid_schedules(
        ranked_courses=candidate_courses,
        unavailable_days=unavailable_days,
        min_credits=min_credits,
        max_credits=max_credits,
        max_courses=max_courses,
        min_required_target=2,
        student_completed_courses=student["completed_courses"],
        credits_completed=float(student.get("credits_completed", 0) or 0),
        return_diagnostics=True,
        limit=120,
    )
    ranked_schedules = rank_schedules(schedules)
    missing_prereq_required_courses = set(
        scheduler_diagnostics.get("blocked_required_by_prereq", [])
    )

    offered_course_codes = {normalize_course_code(c.get("course")) for c in prepared_courses}
    required_not_offered = sorted(
        code for code in remaining_required
        if code not in offered_course_codes
    )

    warnings = []
    if required_not_offered:
        warnings.append("Some required courses are not offered this term.")
    if missing_prereq_required_courses:
        warnings.append("Some required courses are currently blocked by prerequisites.")
    if not ranked_schedules and unavailable_days:
        warnings.append("No schedule matched your availability constraints.")
    if not ranked_schedules and remaining_required:
        warnings.append("Required-course conflicts may require a longer-term plan.")
    if ranked_schedules and len(ranked_schedules) < 3:
        warnings.append("Low schedule availability; try broadening constraints.")

    schedule_cards = []
    for sched in ranked_schedules[:10]:
        ranking = schedule_ranking_details(sched)
        schedule_cards.append({
            "total_credits": total_credits(sched),
            "required_course_count": ranking["required_course_count"],
            "career_alignment_score": ranking["career_alignment_score"],
            "total_recommendation_score": ranking["total_recommendation_score"],
            "workload_balance_penalty": ranking["workload_balance_penalty"],
            "ranking_explanation": ranking["ranking_explanation"],
            "courses": [
                {
                    "course": c["course"],
                    "title": c.get("title") or c.get("course"),
                    "description": c.get("description") or "No description available",
                    "time": c["time"],
                    "credits": extract_credits(c),
                    "reasons": c.get("ranking", {}).get("reasons", []),
                    "course_score": c.get("ranking", {}).get("score", 0),
                    "career_similarity": c.get("ranking", {}).get("career_similarity", 0),
                    "interest_similarity": c.get("ranking", {}).get("interest_similarity", 0),
                    "is_required": c.get("ranking", {}).get("is_required", False),
                }
                for c in sched
            ],
        })

    no_schedule_reason = None
    if not schedule_cards:
        if unavailable_days:
            no_schedule_reason = "No schedules fit your unavailable days with current requirements."
        elif missing_prereq_required_courses:
            no_schedule_reason = "Required courses are blocked by prerequisites this term."
        elif required_not_offered:
            no_schedule_reason = "Required courses are not offered this term."
        else:
            no_schedule_reason = "No valid schedule found under current credit and conflict constraints."

    return jsonify({
        "schedules": schedule_cards,
        "requirement_summary": {
            "remaining_required_courses": remaining_required,
            "remaining_major_courses": requirement_state["remaining_major_courses"],
            "remaining_core_courses": requirement_state["remaining_core_courses"],
            "unsatisfied_core_requirements": requirement_state["unsatisfied_core_requirements"],
            "remaining_required_count": len(remaining_required),
            "remaining_major_count": len(requirement_state["remaining_major_courses"]),
            "remaining_core_count": len(requirement_state["remaining_core_courses"]),
        },
        "edge_cases": {
            "missing_prereq_required_courses": sorted(missing_prereq_required_courses),
            "required_courses_not_offered": required_not_offered,
            "conflict_or_low_availability_warning": len(ranked_schedules) < 3,
            "no_schedule_reason": no_schedule_reason,
        },
        "warnings": warnings,
    })

@app.route("/majors")
def get_majors():
    """
    Returns all available majors from programs_all.json
    """
    return jsonify(list(PROGRAMS.keys()))

# =========================
# RUN SERVER
# =========================

if __name__ == "__main__":
    app.run(debug=True)