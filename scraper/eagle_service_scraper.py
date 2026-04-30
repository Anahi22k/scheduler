import requests
from bs4 import BeautifulSoup
import json
import math
import time
from pathlib import Path

BASE_URL = "https://eagleservice.american.edu"
SEARCH_PAGE = f"{BASE_URL}/student/Courses/SearchResult"
POST_ENDPOINT = f"{BASE_URL}/student/Courses/PostSearchCriteria"
SECTIONS_ENDPOINT = f"{BASE_URL}/student/Courses/Sections"
SECTION_DETAILS_ENDPOINT = f"{BASE_URL}/student/Courses/SectionDetails"


TERM_CODE = "2026S"
PAGE_SIZE = 30


# ---------------------------
# TOKEN
# ---------------------------
def get_verification_token(session):
    response = session.get(SEARCH_PAGE)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    token = soup.find("input", {"name": "__RequestVerificationToken"})

    if not token:
        raise Exception("Token not found")

    return token["value"]


# ---------------------------
# FETCH COURSE PAGES
# ---------------------------
def fetch_page(session, token, page_number):
    payload = {
        "terms": [TERM_CODE],
        "pageNumber": page_number,
        "quantityPerPage": PAGE_SIZE,
        "searchResultsView": "CatalogListing",
        "sortDirection": "Ascending",
        "sortOn": "SectionName"
    }

    headers = {
        "Content-Type": "application/json",
        "__RequestVerificationToken": token,
        "X-Requested-With": "XMLHttpRequest",
        "Referer": SEARCH_PAGE,
        "User-Agent": "Mozilla/5.0"
    }

    #res = session.post(POST_ENDPOINT, json=payload, headers=headers)
    #res.raise_for_status()

    res = session.post(POST_ENDPOINT, json=payload, headers=headers)
    print(res.status_code)
    print(res.text[:500])  # preview response

    return res.json()


# ---------------------------
# FETCH SECTIONS
# ---------------------------

def fetch_sections(session, token, course_id):
    payload = {
        "courseId": course_id,
        "termId": TERM_CODE
    }

    headers = {
        "Content-Type": "application/json; charset=UTF-8",
        "__RequestVerificationToken": token,
        "X-Requested-With": "XMLHttpRequest",
        "Referer": SEARCH_PAGE,
        "Origin": BASE_URL,
        "User-Agent": "Mozilla/5.0"
    }

    res = session.post(SECTIONS_ENDPOINT, json=payload, headers=headers)
    res.raise_for_status()

    return res.json()
# ---------------------------
# FETCH SECTION IDs for A COURSE 
# ---------------------------


# ---------------------------
# FETCH SECTION DETAILS 
# ---------------------------

def fetch_section_details(session, token, section_id):
    payload = {
        "sectionId": section_id,
        "studentId": None
    }

    headers = {
        "Content-Type": "application/json",
        "__RequestVerificationToken": token,
        "X-Requested-With": "XMLHttpRequest",
        "Referer": SEARCH_PAGE,
        "Origin": BASE_URL,
        "User-Agent": "Mozilla/5.0"
    }

    res = session.post(SECTION_DETAILS_ENDPOINT, json=payload, headers=headers)
    res.raise_for_status()

    return res.json()

# ---------------------------
# MAIN SCRAPER
# ---------------------------
def scrape():
    session = requests.Session()

    print("Getting token...")
    token = get_verification_token(session)

    print("Fetching first page...")
    first = fetch_page(session, token, 1)

    total_pages = math.ceil(first["TotalItems"] / PAGE_SIZE)
    courses = first["Courses"]

    # Fetch all pages
    for p in range(2, total_pages + 1):
        print(f"Page {p}/{total_pages}")
        courses.extend(fetch_page(session, token, p)["Courses"])
        time.sleep(0.3)

    print("Fetching sections + details...")

    final_data = []

    for i, course in enumerate(courses):
        course_id = course.get("Id")

        if not course_id:
            continue

        try:
            # 🔥 NEW STEP
            section_ids = course.get("MatchingSectionIds", [])

            if not section_ids:
                continue

            for section_id in section_ids:

                if not section_id:
                    continue

                # 🔥 FINAL STEP
                details = fetch_section_details(session, token, section_id)

                if not details or not isinstance(details, dict):
                    continue

                instructors = details.get("InstructorItems", [])
                times = details.get("TimeLocationItems", [])

                final_data.append({
                    "course": f"{course.get('SubjectCode')}-{course.get('Number')}",
                    "title": course.get("Title"),
                    "description": course.get("Description"),

                    "section_id": section_id,
                    "term": details.get("TermId"),

                    "seats_available": details.get("Available"),

                    "instructor": instructors[0]["Name"] if instructors else None,
                    "email": instructors[0]["EmailAddresses"][0] if instructors and instructors[0]["EmailAddresses"] else None,

                    "time": times[0]["Time"] if times else None,
                    "location": times[0]["Location"] if times else None,
                    "dates": times[0]["Dates"] if times else None
                })

                time.sleep(0.1)

        except Exception as e:
            print(f"Error for course {course_id}: {e}")

        if i % 25 == 0:
            print(f"Processed {i}/{len(courses)} | Collected: {len(final_data)}")

    return final_data
# ---------------------------
# SAVE
# ---------------------------
def save(data):
    path = Path("courses_clean.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"Saved {len(data)} records")

# there was a total of Saved 3480 records
# ---------------------------
# RUN
# ---------------------------
if __name__ == "__main__":
    data = scrape()
    save(data)