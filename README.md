API scraper:

Data contains:

* 1,713 Spring 2026 courses
* Full pagination handled
* Anti-forgery token handled
* Clean local storage

[ app.py ]        → handles requests (API layer)
[ scheduler.py ]  → does the logic (brain)

    “Given what a student has taken… what should they take next?”
[ data/*.json ]   → stores data (memory)
