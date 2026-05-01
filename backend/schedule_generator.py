import re
from collections import defaultdict


DAY_TOKENS = ["Su", "Sa", "M", "T", "W", "R", "F"]


def extract_credits(course):
    desc = course.get("description", "") or ""
    match = re.search(r"\((\d+(?:\.\d+)?)", desc)
    return float(match.group(1)) if match else 3.0


def split_days(day_segment):
    normalized = (
        day_segment.replace("Mon", "M")
        .replace("Tue", "T")
        .replace("Wed", "W")
        .replace("Thu", "R")
        .replace("Fri", "F")
        .replace("Sat", "Sa")
        .replace("Sun", "Su")
        .replace(",", " ")
    )
    return re.findall(r"Sa|Su|M|T|W|R|F", normalized)


def _to_minutes(hour, minute, meridiem):
    hour = int(hour)
    minute = int(minute)
    if meridiem == "PM" and hour != 12:
        hour += 12
    if meridiem == "AM" and hour == 12:
        hour = 0
    return hour * 60 + minute


def parse_time_blocks(time_str):
    raw = (time_str or "").strip()
    if not raw or "TBD" in raw:
        return []

    match = re.search(
        r"([A-Za-z,\s]+)\s+(\d{1,2}):(\d{2})\s*(AM|PM)\s*-\s*(\d{1,2}):(\d{2})\s*(AM|PM)",
        raw,
    )
    if not match:
        return []

    day_segment, sh, sm, sap, eh, em, eap = match.groups()
    days = split_days(day_segment)
    start = _to_minutes(sh, sm, sap)
    end = _to_minutes(eh, em, eap)
    return [{"day": d, "start": start, "end": end} for d in days]


def parse_prereq_text(course):
    description = course.get("description", "") or ""
    prereq = re.search(r"Prerequisite(?:/Concurrent)?:\s*(.*?)(?:\.|$)", description)
    return prereq.group(1).strip() if prereq else ""


def prereq_allows_course(course, completed_courses, credits_completed):
    prereq_text = parse_prereq_text(course)
    prereq_text_lower = prereq_text.lower()
    required_codes = re.findall(r"[A-Z]{3,4}-\d{3}", prereq_text.upper())
    has_explicit_prereq_data = bool(prereq_text.strip())

    # Missing prereq data means unknown/open and should not block enrollment.
    if not has_explicit_prereq_data:
        return True

    if "junior standing" in prereq_text_lower or "senior standing" in prereq_text_lower:
        return False

    if required_codes and "concurrent" not in prereq_text_lower:
        or_groups = re.split(r"\bor\b", prereq_text_lower)
        group_satisfied = False
        for group in or_groups:
            group_codes = re.findall(r"[A-Z]{3,4}-\d{3}", group.upper())
            if group_codes and all(code in completed_courses for code in group_codes):
                group_satisfied = True
                break
        if not group_satisfied:
            return False

    if "credit" in prereq_text_lower and "hour" in prereq_text_lower:
        credit_match = re.search(r"(\d+)", prereq_text_lower)
        if credit_match and credits_completed < int(credit_match.group(1)):
            return False

    return True


def prepare_courses(courses):
    prepared = []
    for course in courses:
        updated = dict(course)
        updated["parsed_time"] = parse_time_blocks(course.get("time", ""))
        updated["credits"] = extract_credits(course)
        prepared.append(updated)
    return prepared


def conflicts(a_blocks, b_blocks):
    for a in a_blocks:
        for b in b_blocks:
            if a["day"] == b["day"] and not (a["end"] <= b["start"] or b["end"] <= a["start"]):
                return True
    return False


def respects_unavailable_days(course, unavailable_days):
    blocked = set(unavailable_days or [])
    if not blocked:
        return True
    if not course.get("parsed_time"):
        return False
    return all(block["day"] not in blocked for block in course["parsed_time"])


def filter_schedulable_courses(courses, unavailable_days):
    return [
        c for c in courses
        if c.get("parsed_time")
        and (c.get("seats_available") or 0) > 0
        and respects_unavailable_days(c, unavailable_days)
    ]


def group_sections_by_course(courses):
    grouped = defaultdict(list)
    for course in courses:
        grouped[course["course"]].append(course)
    return list(grouped.values())


def total_credits(schedule):
    return sum(c.get("credits", 0.0) for c in schedule)


def generate_valid_schedules(
    ranked_courses,
    unavailable_days=None,
    min_credits=12.0,
    max_credits=17.0,
    max_courses=5,
    min_required_target=2,
    student_completed_courses=None,
    credits_completed=0,
    return_diagnostics=False,
    limit=40,
):
    completed_set = {str(c).strip().upper() for c in (student_completed_courses or []) if c}
    schedulable = filter_schedulable_courses(ranked_courses, unavailable_days or [])
    course_groups = group_sections_by_course(schedulable)

    required_groups = [
        group for group in course_groups
        if any(c.get("ranking", {}).get("is_required") for c in group)
    ]
    optional_groups = [
        group for group in course_groups
        if not any(c.get("ranking", {}).get("is_required") for c in group)
    ]

    # Required groups are always evaluated before optional groups.
    required_groups.sort(
        key=lambda group: max(c.get("ranking", {}).get("score", 0) for c in group),
        reverse=True,
    )
    optional_groups.sort(
        key=lambda group: max(c.get("ranking", {}).get("score", 0) for c in group),
        reverse=True,
    )
    ordered_groups = required_groups + optional_groups

    schedules = []
    blocked_required_by_prereq = set()

    for group in required_groups:
        group_code = group[0].get("course")
        if not any(prereq_allows_course(section, completed_set, credits_completed) for section in group):
            blocked_required_by_prereq.add(group_code)

    def backtrack(index, current):
        if len(schedules) >= limit:
            return

        credits_now = total_credits(current)
        if credits_now > max_credits:
            return

        if index >= len(ordered_groups) or len(current) >= max_courses:
            if min_credits <= credits_now <= max_credits:
                schedules.append(list(current))
            return

        group = ordered_groups[index]
        group_is_required = any(c.get("ranking", {}).get("is_required") for c in group)
        can_place_any_section = any(
            prereq_allows_course(section, completed_set, credits_completed)
            and
            not any(conflicts(section["parsed_time"], chosen["parsed_time"]) for chosen in current)
            and (credits_now + section.get("credits", 0.0)) <= max_credits
            for section in group
        )

        # Required groups are only skipped when no section can be placed due to conflicts/limits.
        if not group_is_required or not can_place_any_section:
            backtrack(index + 1, current)

        # Option: choose one section from this course code.
        for section in group:
            if not prereq_allows_course(section, completed_set, credits_completed):
                continue
            if any(conflicts(section["parsed_time"], chosen["parsed_time"]) for chosen in current):
                continue
            current.append(section)
            backtrack(index + 1, current)
            current.pop()

    backtrack(0, [])

    offered_required_count = len(required_groups)
    if offered_required_count == 0 or not schedules:
        if return_diagnostics:
            return schedules, {"blocked_required_by_prereq": sorted(blocked_required_by_prereq)}
        return schedules

    required_count_per_schedule = [
        sum(1 for c in sched if c.get("ranking", {}).get("is_required"))
        for sched in schedules
    ]
    best_required_count = max(required_count_per_schedule, default=0)
    min_required_enforced = min(min_required_target, offered_required_count, best_required_count)

    filtered = [
        sched for sched in schedules
        if sum(1 for c in sched if c.get("ranking", {}).get("is_required")) >= min_required_enforced
    ]
    final_schedules = filtered if filtered else schedules
    if return_diagnostics:
        return final_schedules, {"blocked_required_by_prereq": sorted(blocked_required_by_prereq)}
    return final_schedules


def rank_schedules(schedules):
    def schedule_key(schedule):
        required_count = sum(1 for c in schedule if c.get("ranking", {}).get("is_required"))
        career_score = sum(c.get("ranking", {}).get("career_similarity", 0.0) for c in schedule)
        total_score = sum(c.get("ranking", {}).get("score", 0.0) for c in schedule)
        credits = total_credits(schedule)
        workload_balance = -abs(15.0 - credits)
        return (required_count, career_score, workload_balance, total_score)

    ranked = list(schedules)
    ranked.sort(key=schedule_key, reverse=True)
    return ranked
