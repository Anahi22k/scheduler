import requests
from bs4 import BeautifulSoup
from ug_majors import UG_MAJORS
import re
import json

BASE = "https://catalog.american.edu"
URL = "https://catalog.american.edu/content.php?catoid=21&navoid=3749"


def normalize(text):
    return text.strip().lower()


# =========================
# STEP 1: GET ONLY UG LINKS
# =========================
def get_program_links():
    res = requests.get(URL)
    soup = BeautifulSoup(res.text, "html.parser")

    links = []
    seen = set()

    normalized_majors = [normalize(m) for m in UG_MAJORS]

    for a in soup.find_all("a"):
        href = a.get("href")
        text = a.text.strip()

        if not href or "preview_program.php" not in href:
            continue

        if normalize(text) in normalized_majors:
            full_url = BASE + "/" + href

            if full_url not in seen:
                links.append((text, full_url))
                seen.add(full_url)

    print(f"Found {len(links)} UG majors")
    return links


# =========================
# STEP 2: EXTRACT ALL COURSES
# =========================
def extract_all_courses(text):
    return list(set(re.findall(r"[A-Z]{2,4}-\d{3}", text)))


# =========================
# STEP 3: SCRAPE ALL MAJORS
# =========================
def scrape_all():
    programs = {}
    links = get_program_links()

    for name, url in links:
        print("Scraping:", name)

        res = requests.get(url)
        soup = BeautifulSoup(res.text, "html.parser")

        # get main content only
        content = soup.find("div", {"id": "acalog-content"})
        text = content.get_text() if content else soup.get_text()

        courses = extract_all_courses(text)

        programs[name] = {
            "all_courses": courses
        }

    return programs


# =========================
# STEP 4: SAVE FILE
# =========================
def save_programs(programs):
    with open("backend/data/programs/programs_all.json", "w") as f:
        json.dump(programs, f, indent=2)


# =========================
# RUN
# =========================
if __name__ == "__main__":
    programs = scrape_all()
    save_programs(programs)