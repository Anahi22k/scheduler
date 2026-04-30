import { useState, useEffect } from "react";

export default function App() {
  // majors now come from backend
  const [majors, setMajors] = useState([]);

  const [major, setMajor] = useState("");
  const [unavailableDays, setUnavailableDays] = useState([]);
  const [schedules, setSchedules] = useState([]);
  const [interests, setInterests] = useState("");
  const [loading, setLoading] = useState(false);
  const [completedCourses, setCompletedCourses] = useState("");
  const [creditsCompleted, setCreditsCompleted] = useState(0);

  // career selection
  const [career, setCareer] = useState("");
  const [careerInput, setCareerInput] = useState("");
  const [careerOptions, setCareerOptions] = useState([]);

  // backend day format
  const days = ["M", "T", "W", "R", "F", "Sa", "Su"];

  const dayLabels = {
    M: "Mon",
    T: "Tue",
    W: "Wed",
    R: "Thu",
    F: "Fri",
    Sa: "Sat",
    Su: "Sun"
  };

  // fetch career options
  useEffect(() => {
    fetch("http://127.0.0.1:5000/careers")
      .then(res => res.json())
      .then(data => setCareerOptions(data))
      .catch(err => console.error(err));
  }, []);

  // fetch majors dynamically from backend
  useEffect(() => {
    fetch("http://127.0.0.1:5000/majors")
      .then(res => res.json())
      .then(data => setMajors(data))
      .catch(err => console.error(err));
  }, []);

  // filter career dropdown
  const filteredCareers = careerOptions
    .filter(c => c.toLowerCase().includes(careerInput.toLowerCase()))
    .sort((a, b) =>
      a.toLowerCase().indexOf(careerInput.toLowerCase()) -
      b.toLowerCase().indexOf(careerInput.toLowerCase())
    )
    .slice(0, 10);

  // toggle unavailable days
  const toggleDay = (day) => {
    setUnavailableDays((prev) =>
      prev.includes(day)
        ? prev.filter((d) => d !== day)
        : [...prev, day]
    );
  };

  // call backend to generate schedules
  const generateSchedules = async () => {
    setLoading(true);

    try {
      const res = await fetch("http://127.0.0.1:5000/generate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          major,
          unavailable_days: unavailableDays,
          interests,
          career,
          credits_completed: creditsCompleted,
          completed_courses: completedCourses
            .split(",")
            .map(c => c.trim().toUpperCase())
            .filter(c => c !== ""),
          max_courses: 5,
        }),
      });

      if (!res.ok) throw new Error("Server error");

      const data = await res.json();
      setSchedules(data.schedules || []);
    } catch (err) {
      console.error(err);
      alert("Something went wrong. Check backend.");
    }

    setLoading(false);
  };

  return (
    <div style={{ padding: "30px", maxWidth: "900px", margin: "auto" }}>
      <h1 style={{ textAlign: "center" }}>Schedule Builder</h1>

      {/* MAJOR SELECTION */}
      <div style={{ marginBottom: "20px" }}>
        <label><strong>Major:</strong></label><br />
        <select value={major} onChange={(e) => setMajor(e.target.value)}>
          <option value="">Select Major</option>
          {majors.map((m) => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
      </div>

      {/* INTEREST INPUT */}
      <div style={{ marginBottom: "20px" }}>
        <label><strong>Interests</strong></label><br />
        <textarea
          placeholder="Example: data, business, helping people..."
          value={interests}
          onChange={(e) => setInterests(e.target.value)}
          rows={3}
          style={{ width: "100%" }}
        />
      </div>

      {/* CAREER SEARCH */}
      <div style={{ marginBottom: "20px" }}>
        <label><strong>Career Goal</strong></label><br />
        <input
          placeholder="Type to search careers..."
          value={careerInput}
          onChange={(e) => setCareerInput(e.target.value)}
          style={{ width: "100%" }}
        />

        {careerInput && (
          <div
            style={{
              border: "1px solid #ccc",
              maxHeight: "150px",
              overflowY: "auto",
              background: "white"
            }}
          >
            {filteredCareers.map((c) => (
              <div
                key={c}
                style={{ padding: "8px", cursor: "pointer" }}
                onClick={() => {
                  setCareer(c);
                  setCareerInput("");
                }}
              >
                {c}
              </div>
            ))}
          </div>
        )}

        {career && (
          <p style={{ fontSize: "12px", color: "gray" }}>
            Selected: {career}
          </p>
        )}
      </div>

      {/* COMPLETED COURSES */}
      <div style={{ marginBottom: "20px" }}>
        <label><strong>Courses you've taken</strong></label><br />
        <input
          placeholder="Example: ACCT-245, CSC-148"
          value={completedCourses}
          onChange={(e) => setCompletedCourses(e.target.value)}
          style={{ width: "100%" }}
        />
      </div>

      {/* CREDITS COMPLETED */}
      <div style={{ marginBottom: "20px" }}>
        <label><strong>Credits Completed</strong></label><br />
        <input
          type="number"
          value={creditsCompleted}
          onChange={(e) => setCreditsCompleted(Number(e.target.value))}
          style={{ width: "100%" }}
        />
      </div>

      {/* UNAVAILABLE DAYS */}
      <div style={{ marginBottom: "20px" }}>
        <strong>Unavailable Days:</strong><br />
        {days.map((d) => (
          <label key={d} style={{ marginRight: "10px" }}>
            <input type="checkbox" onChange={() => toggleDay(d)} />
            {dayLabels[d]}
          </label>
        ))}
      </div>

      {/* GENERATE BUTTON */}
      <button onClick={generateSchedules} disabled={loading || !major}>
        {loading ? "Generating..." : "Generate Schedule"}
      </button>

      {/* RESULTS */}
      <h2 style={{ marginTop: "30px", textAlign: "center" }}>
        Top Schedules
      </h2>

      {!loading && schedules.length === 0 && (
        <p style={{ textAlign: "center" }}>
          No schedules yet. Try generating one.
        </p>
      )}

      <div
        style={{
          display: "flex",
          overflowX: "auto",
          gap: "20px",
          padding: "20px 0"
        }}
      >
        {schedules.map((sched, i) => (
          <div
            key={i}
            style={{
              minWidth: "320px",
              padding: "20px",
              border: i === 0 ? "2px solid hotpink" : "1px solid #ccc",
              borderRadius: "12px",
              background: "#111",
              color: "white"
            }}
          >
            <h4 style={{ textAlign: "center" }}>
              {i === 0 ? "Best Schedule" : `Schedule ${i + 1}`}
            </h4>

            {sched.courses.map((c, idx) => (
              <div key={idx} style={{ marginBottom: "12px" }}>
                <strong>{c.course}</strong> ({c.credits} credits) — {c.time}

                {c.reasons && c.reasons.length > 0 && (
                  <ul style={{
                    fontSize: "12px",
                    marginTop: "6px",
                    color: "#bbb",
                    paddingLeft: "16px"
                  }}>
                  {c.reasons.map((r, i) => (
                    <li key={i}>{r}</li>
                  ))}
              </ul>
              )}
            </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}