
import re
from collections import defaultdict
from rapidfuzz import fuzz, utils

# =========================
# TIME PARSING
# =========================

def split_days(day_str):
    return re.findall(r"Sa|Su|M|T|W|R|F", day_str)

def parse_time(time_str):
    if not time_str or "TBD" in time_str:
        return []

    match = re.match(
        r"([MTWRFSaSu]+)\s(\d+):(\d+)\s(AM|PM)\s-\s(\d+):(\d+)\s(AM|PM)",
        time_str
    )

    if not match:
        return []

    day_str, sh, sm, sap, eh, em, eap = match.groups()

    def to_minutes(h, m, ap):
        h = int(h)
        m = int(m)
        if ap == "PM" and h != 12:
            h += 12
        if ap == "AM" and h == 12:
            h = 0
        return h * 60 + m

    start = to_minutes(sh, sm, sap)
    end = to_minutes(eh, em, eap)

    days = split_days(day_str)

    return [{"day": d, "start": start, "end": end} for d in days]

# =========================
# TIME PREFERENCE SCORING
# =========================

def time_score(course):
    score = 0
    for t in course.get("parsed_time", []):
        hour = t["start"] // 60

        if 10 <= hour <= 15:
            score += 2

        if hour < 9 or hour > 18:
            score -= 2

    return score

# =========================
# CREDITS
# =========================

def extract_credits(course):
    desc = course.get("description", "")
    match = re.search(r"\((\d+(?:\.\d+)?)", desc)
    return float(match.group(1)) if match else 3.0

def total_credits(schedule):
    return sum(extract_credits(c) for c in schedule)

def valid_credit_load(schedule):
    total = total_credits(schedule)
    return 12.5 <= total <= 17.5

# =========================
# CONFLICT DETECTION
# =========================

def conflicts(a_list, b_list):
    for a in a_list:
        for b in b_list:
            if a["day"] == b["day"]:
                if not (a["end"] <= b["start"] or b["end"] <= a["start"]):
                    return True
    return False

# =========================
# PREP COURSES
# =========================

def prepare_courses(courses):
    prepared = []
    for c in courses:
        new_c = c.copy()
        new_c["parsed_time"] = parse_time(c.get("time"))
        prepared.append(new_c)
    return prepared

# =========================
# GROUP BY COURSE (CRITICAL)
# =========================

def group_by_course(courses, career=None):
    grouped = defaultdict(list)

    for c in courses:
        grouped[c["course"]].append(c)

    groups = list(grouped.values())

    # prioritize career sections inside each course
    if career:
        for group in groups:
            group.sort(
                key=lambda c: matches_career(c, career),
                reverse=True
            )

    return groups
# =========================
# SCHEDULE GENERATION
# =========================

def generate_schedules(course_groups, max_courses=5, limit=500):
    results = []

    def backtrack(index, current):
        if len(results) >= limit:
            return

        if len(current) == max_courses:
            if valid_credit_load(current):
                results.append(list(current))
            return

        if index >= len(course_groups):
            return

        for section in course_groups[index]:
            if all(not conflicts(section["parsed_time"], c["parsed_time"]) for c in current):
                current.append(section)
                backtrack(index + 1, current)
                current.pop()

        backtrack(index + 1, current)

    backtrack(0, [])
    return results

# =========================
# ELIGIBILITY RULES
# =========================

def parse_rules(course):
    desc = course.get("description", "")
    prereq = re.search(r"Prerequisite(?:/Concurrent)?:\s*(.*?)(?:\.|$)", desc)
    restriction = re.search(r"Restriction:(.*?)(?:\.|$)", desc)

    return {
        "prereq": prereq.group(1).strip() if prereq else None,
        "restriction": restriction.group(1).strip() if restriction else None
    }

def is_eligible(course, student):
    rules = parse_rules(course)
    completed = set(student.get("completed_courses", []))

    #  don't recommend courses already taken
    if course["course"] in completed:
        return False

    prereq_text = (rules["prereq"] or "").lower()

    # filter out upper-level standing (your design choice)
    if "junior standing" in prereq_text:
        return False
    if "senior standing" in prereq_text:
        return False

    # =========================
    # HANDLE COURSE PREREQS
    # =========================
    if rules["prereq"]:
        # extract all course codes
        all_courses = re.findall(r"[A-Z]{3,4}-\d{3}", rules["prereq"])

        # if it's concurrent → allow even if not completed
        if "concurrent" not in prereq_text:
            # split by OR
            or_groups = re.split(r"\bor\b", prereq_text)

            valid = False

            for group in or_groups:
                group_courses = re.findall(r"[A-Z]{3,4}-\d{3}", group.upper())

                # must satisfy ALL in this group
                if all(c in completed for c in group_courses):
                    valid = True
                    break

            if not valid and all_courses:
                return False

    # =========================
    # CREDIT HOURS
    # =========================
    if "credit hours" in prereq_text:
        match = re.search(r"\d+", prereq_text)
        if match and student.get("credits_completed", 0) < int(match.group()):
            return False

    # =========================
    # RESTRICTIONS
    # =========================
    if rules["restriction"]:
        if student["major"].lower() not in rules["restriction"].lower():
            return False

    return True
# =========================
# MATCHING
# =========================

def matches_interest(course, interests):
    if not interests:
        return False

    text = utils.default_process(course.get("title", "") + " " + course.get("description", ""))
    interests = utils.default_process(interests)

    return fuzz.WRatio(interests, text) > 60

def matches_career(course, career_text):
    if not career_text:
        return False

    text = utils.default_process(course.get("title", "") + " " + course.get("description", ""))
    career_text = utils.default_process(career_text)

    score = fuzz.WRatio(career_text, text)
    keywords = ["data", "analysis", "security", "forensics"]

    return score > 60 and any(k in text for k in keywords)

# =========================
# AVAILABILITY
# =========================

def respects_unavailable_days(course, days):
    # block courses with unknown/bad time parsing
    if not course["parsed_time"]:
        return False

    return all(t["day"] not in days for t in course["parsed_time"])
# =========================
# FINAL SCORING
# =========================


def score_schedule(schedule, interests, career, program):
    score = 0
    credits = total_credits(schedule)

    for c in schedule:
        score += time_score(c)

        # prioritize major courses
        if c["course"] in program.get("all_courses", []):
            score += 3

        if matches_interest(c, interests):
            score += 2

        if matches_career(c, career):
            score += 5

    if 12 <= credits <= 17:
        score += 3
    else:
        score -= 3

    return score
