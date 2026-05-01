from rapidfuzz import fuzz, utils


REQUIRED_WEIGHT = 100.0
CAREER_WEIGHT = 35.0
INTEREST_WEIGHT = 20.0
SEAT_WEIGHT = 5.0


def _normalize_text(text):
    return utils.default_process(text or "")


def _course_text(course):
    return _normalize_text(
        f"{course.get('course', '')} {course.get('title', '')} {course.get('description', '')}"
    )


def compute_text_similarity(query_text, course):
    if not query_text:
        return 0.0
    return float(fuzz.token_set_ratio(_normalize_text(query_text), _course_text(course)))


def score_course(
    course,
    remaining_required_courses,
    career_text="",
    interests_text="",
):
    code = (course.get("course") or "").upper()
    is_required = code in remaining_required_courses
    career_score = compute_text_similarity(career_text, course)
    interest_score = compute_text_similarity(interests_text, course)
    seats = max(0, int(course.get("seats_available") or 0))

    score = 0.0
    reasons = []

    if is_required:
        score += REQUIRED_WEIGHT
        reasons.append("Required for major or AU Core")

    if career_score >= 45:
        score += (career_score / 100.0) * CAREER_WEIGHT
        reasons.append("Aligned with career goal")

    if interest_score >= 40:
        score += (interest_score / 100.0) * INTEREST_WEIGHT
        reasons.append("Matches your interests")

    if seats > 0:
        score += min(SEAT_WEIGHT, seats / 20.0)

    return {
        "score": round(score, 3),
        "is_required": is_required,
        "career_similarity": round(career_score, 2),
        "interest_similarity": round(interest_score, 2),
        "reasons": reasons,
    }


def rank_courses(courses, remaining_required_courses, career_text="", interests_text=""):
    remaining_set = set(remaining_required_courses)
    ranked = []

    for course in courses:
        details = score_course(
            course=course,
            remaining_required_courses=remaining_set,
            career_text=career_text,
            interests_text=interests_text,
        )
        enriched = dict(course)
        enriched["ranking"] = details
        ranked.append(enriched)

    ranked.sort(
        key=lambda c: (
            c["ranking"]["is_required"],
            c["ranking"]["score"],
            c.get("seats_available") or 0,
        ),
        reverse=True,
    )
    return ranked
