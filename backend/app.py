from flask import Flask, request, jsonify
from flask_cors import CORS
import json


from scheduler import (
    prepare_courses,
    generate_schedules,
    group_by_course,
    is_eligible,
    matches_interest,
    matches_career,
    respects_unavailable_days,
    score_schedule,
    extract_credits,
    total_credits
)

app = Flask(__name__)
CORS(app)

# =========================
# LOAD DATA
# =========================

# Load all course offerings
with open("backend/data/courses_clean.json") as f:
    courses = json.load(f)

# Load career data (used for career-based recommendations)
with open("backend/data/onet_careers.json") as f:
    careers = json.load(f)

# Load AU Core requirements
with open("backend/data/programs/au_core.json") as f:
    au_core = json.load(f)

# Load ALL majors (generated from scraper)
# Each major contains: { "all_courses": [...] }
with open("backend/data/programs/programs_all.json") as f:
    PROGRAMS = json.load(f)

# Preprocess course time data once at startup
prepared_courses = prepare_courses(courses)

# =========================
# HELPER FUNCTIONS
# =========================

def relevant_to_major(course, program):
    """
    Returns True if the course belongs to the selected major.
    Uses the 'all_courses' list generated from the catalog.
    """
    return course["course"] in program.get("all_courses", [])


def needed_for_core(course, core, student):
    """
    Determines whether a course satisfies AU Core requirements.
    """
    completed = set(student.get("completed_courses", []))
    code = course["course"]

    for req in core["requirements"]:
        if req["type"] == "choose_one":
            if code in req["courses"] and code not in completed:
                return True

        elif req["type"] == "choose_sequence":
            for seq in req["options"]:
                if code in seq and code not in completed:
                    return True

        elif req["type"] == "tag_based":
            if req["tag"] in course.get("tags", []):
                return True

    return False

def get_course_reasons(course, student, program, interests, career):
    """
    Returns a list of human-readable reasons why a course was selected.
    """
    reasons = []

    if relevant_to_major(course, program):
        reasons.append("Required or part of your major")

    if needed_for_core(course, au_core, student):
        reasons.append("Fulfills AU Core requirement")

    if matches_interest(course, interests):
        reasons.append("Matches your interests")

    if matches_career(course, career):
        reasons.append("Aligned with your career goal")

    return reasons
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
    print("RAW:", data.get("unavailable_days"))  
    #  Map frontend days → backend format
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

    print("MAPPED:", unavailable_days) 
    

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

    if not program:
        print("Warning: Major not found in PROGRAMS:", student["major"])

    interests = data.get("interests", "")
    career = data.get("career", "").lower()
    max_courses = data.get("max_courses", 5)

    # =========================
    # FILTER ELIGIBLE COURSES
    # =========================

    eligible = [
        c for c in prepared_courses
        if is_eligible(c, student)
        and respects_unavailable_days(c, unavailable_days)
        and not c["course"].startswith("AUAB")
        and (
            # Course belongs to student's major
            relevant_to_major(c, program)

            # OR satisfies AU Core
            or needed_for_core(c, au_core, student)

            # OR matches interest keywords
            or matches_interest(c, interests)

            # OR matches career goals
            or matches_career(c, career)
        )
    ]
    eligible.sort(
        key=lambda c: matches_career(c, career),
        reverse=True
    )
    # Fallback if filtering is too strict
    if not eligible:
        eligible = [
            c for c in prepared_courses
            if is_eligible(c, student)
            and respects_unavailable_days(c, unavailable_days)
        ]

    # =========================
    # GENERATE SCHEDULES
    # =========================

    grouped = group_by_course(eligible, career)
    grouped.sort(
        key=lambda group: any(matches_career(c, career) for c in group),
        reverse=True
    )

    schedules = generate_schedules(
        grouped,
        max_courses=max_courses
    )

    # =========================
    # RANK SCHEDULES
    # =========================

    schedules.sort(
        key=lambda s: score_schedule(s, interests, career, program),
        reverse=True
    )

    # =========================
    # RETURN TOP RESULTS
    # =========================

    return jsonify({
        "schedules": [
            {
                "total_credits": total_credits(sched),
                "courses": [
                    {
                        "course": c["course"],
                        "time": c["time"],
                        "credits": extract_credits(c),
                        "reasons": get_course_reasons(
                            c,
                            student,
                            program,
                            interests,
                            career
                        )
                    }
                    for c in sched
                ] 
            }
            for sched in schedules[:10]
        ]
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