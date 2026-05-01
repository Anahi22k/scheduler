import re
from collections import defaultdict


CORE_NAME_TO_TAG = {
    "Writing II": "W2",
    "Quantitative Literacy I": "Q1",
    "Quantitative Literacy II": "Q2",
    "Diversity and Equity": "DE",
}


def normalize_course_code(code):
    return (code or "").strip().upper()


def extract_core_tags_from_description(description):
    text = description or ""
    tags = set()

    for name, tag in CORE_NAME_TO_TAG.items():
        if name.lower() in text.lower():
            tags.add(tag)

    return tags


def build_course_index(courses):
    by_code = defaultdict(list)
    for course in courses:
        by_code[normalize_course_code(course.get("course"))].append(course)
    return by_code


def get_major_required_courses(programs, major):
    program = programs.get(major, {})
    return {normalize_course_code(c) for c in program.get("all_courses", []) if c}


def _unsatisfied_core_requirements(au_core, completed, course_index):
    unsatisfied = []
    remaining_codes = set()

    for req in au_core.get("requirements", []):
        req_type = req.get("type")
        req_name = req.get("name", "Unnamed Core Requirement")

        if req_type == "choose_one":
            options = {normalize_course_code(c) for c in req.get("courses", [])}
            if not (options & completed):
                unsatisfied.append(req_name)
                remaining_codes.update(options)

        elif req_type == "choose_sequence":
            sequences = [
                [normalize_course_code(c) for c in seq]
                for seq in req.get("options", [])
            ]
            sequence_satisfied = any(all(code in completed for code in seq) for seq in sequences)
            if not sequence_satisfied:
                unsatisfied.append(req_name)
                for seq in sequences:
                    remaining_codes.update(seq)

        elif req_type == "tag_based":
            tag = req.get("tag")
            if not tag:
                continue

            completed_satisfies_tag = False
            for code in completed:
                for course in course_index.get(code, []):
                    tags = course.get("tags", []) or []
                    parsed_tags = extract_core_tags_from_description(course.get("description", ""))
                    if tag in tags or tag in parsed_tags:
                        completed_satisfies_tag = True
                        break
                if completed_satisfies_tag:
                    break

            if not completed_satisfies_tag:
                unsatisfied.append(req_name)
                for code, offerings in course_index.items():
                    for course in offerings:
                        tags = course.get("tags", []) or []
                        parsed_tags = extract_core_tags_from_description(course.get("description", ""))
                        if tag in tags or tag in parsed_tags:
                            remaining_codes.add(code)
                            break

        elif req_type == "multi_category":
            # Catalog export currently lacks explicit category metadata.
            # We track this requirement as unsatisfied for visibility.
            unsatisfied.append(req_name)

    return unsatisfied, remaining_codes


def build_remaining_requirements(programs, au_core, major, completed_courses, all_courses):
    completed = {normalize_course_code(c) for c in completed_courses if c}
    course_index = build_course_index(all_courses)

    major_required = get_major_required_courses(programs, major)
    remaining_major = sorted(c for c in major_required if c not in completed)

    unsatisfied_core, remaining_core_codes = _unsatisfied_core_requirements(
        au_core=au_core,
        completed=completed,
        course_index=course_index,
    )
    remaining_core = sorted(c for c in remaining_core_codes if c not in completed)

    remaining_required = sorted(set(remaining_major) | set(remaining_core))

    return {
        "remaining_required_courses": remaining_required,
        "remaining_major_courses": remaining_major,
        "remaining_core_courses": remaining_core,
        "unsatisfied_core_requirements": unsatisfied_core,
        "completed_courses_normalized": sorted(completed),
    }
