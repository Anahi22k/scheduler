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
  const [requirementSummary, setRequirementSummary] = useState(null);
  const [warnings, setWarnings] = useState([]);
  const [edgeCases, setEdgeCases] = useState({});
  const [activeCourse, setActiveCourse] = useState(null);

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
      setRequirementSummary(data.requirement_summary || null);
      setWarnings(data.warnings || []);
      setEdgeCases(data.edge_cases || {});
    } catch (err) {
      console.error(err);
      alert("Something went wrong. Check backend.");
    }

    setLoading(false);
  };

  const parsedCompletedCourses = completedCourses
    .split(",")
    .map((c) => c.trim().toUpperCase())
    .filter((c) => c !== "");

  const completedEstimate = parsedCompletedCourses.length;
  const remainingEstimate = requirementSummary?.remaining_required_count || 0;
  const estimatedTotal = completedEstimate + remainingEstimate;
  const progressPct = estimatedTotal > 0
    ? Math.round((completedEstimate / estimatedTotal) * 100)
    : 0;

  const resultWarnings = [];
  if (Array.isArray(warnings)) resultWarnings.push(...warnings);

  if (edgeCases?.required_courses_not_offered?.length) {
    resultWarnings.push(
      `Required courses not offered: ${edgeCases.required_courses_not_offered.slice(0, 8).join(", ")}`
    );
  }
  if (edgeCases?.missing_prereq_required_courses?.length) {
    resultWarnings.push(
      `Missing prerequisites for: ${edgeCases.missing_prereq_required_courses.slice(0, 8).join(", ")}`
    );
  }
  if (edgeCases?.conflict_or_low_availability_warning) {
    resultWarnings.push("Low availability warning: very few valid schedules matched your constraints.");
  }

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

      {(resultWarnings.length > 0 || edgeCases?.no_schedule_reason) && (
        <div
          style={{
            marginTop: "16px",
            marginBottom: "16px",
            padding: "12px",
            border: "1px solid #f1c40f",
            background: "#fff9e6"
          }}
        >
          <strong style={{ color: "#8a6d3b" }}>Warnings & Edge Cases</strong>
          <ul style={{ marginTop: "8px", color: "#8a6d3b" }}>
            {resultWarnings.map((w, idx) => <li key={`warn-${idx}`}>{w}</li>)}
            {edgeCases?.no_schedule_reason && (
              <li style={{ color: "#b00020" }}>
                No valid schedules could be generated because: {edgeCases.no_schedule_reason}
              </li>
            )}
          </ul>
        </div>
      )}

      {requirementSummary && (
        <div
          style={{
            marginTop: "16px",
            marginBottom: "20px",
            padding: "12px",
            border: "1px solid #ddd"
          }}
        >
          <h3 style={{ marginTop: 0, marginBottom: "10px" }}>Requirement Progress</h3>

          <div style={{ marginBottom: "10px" }}>
            <div style={{ fontSize: "14px", marginBottom: "4px" }}>
              Estimated progress: {completedEstimate}/{estimatedTotal} completed ({progressPct}%)
            </div>
            <div style={{ width: "100%", height: "10px", background: "#eee" }}>
              <div
                style={{
                  width: `${progressPct}%`,
                  height: "100%",
                  background: "#4caf50"
                }}
              />
            </div>
          </div>

          <div style={{ marginBottom: "8px" }}>
            <strong>Major Requirements</strong>
            <div>Remaining major courses: {requirementSummary.remaining_major_count ?? 0}</div>
          </div>

          <div>
            <strong>AU Core Requirements</strong>
            <div>Remaining AU core courses: {requirementSummary.remaining_core_count ?? 0}</div>
          </div>

          <div style={{ marginTop: "8px" }}>
            Remaining required courses (total): {requirementSummary.remaining_required_count ?? 0}
          </div>
        </div>
      )}

      {!loading && schedules.length === 0 && (
        <div style={{ textAlign: "center", marginTop: "20px", color: "#b00020" }}>
          No valid schedules could be generated because: {edgeCases?.no_schedule_reason || "constraints could not be satisfied."}
        </div>
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
            <h4 style={{ textAlign: "center", marginBottom: "8px" }}>
              {`Schedule #${i + 1}`}
            </h4>

            <div style={{ fontSize: "13px", color: "#ddd", marginBottom: "8px" }}>
              <div>Total credits: {sched.total_credits}</div>
              <div>Required course count: {sched.required_course_count ?? 0}</div>
              <div>Career alignment score: {sched.career_alignment_score ?? 0}</div>
            </div>

            <div
              style={{
                border: "1px solid #666",
                padding: "8px",
                borderRadius: "6px",
                marginBottom: "12px",
                background: "#1c1c1c"
              }}
            >
              <strong style={{ color: "#ffd54f" }}>Why this schedule?</strong>
              <div style={{ fontSize: "12px", marginTop: "4px", color: "#ddd" }}>
                {sched.ranking_explanation || "Ranked by requirement fit, career match, and workload balance."}
              </div>
            </div>

            {sched.courses.map((c, idx) => (
              <div key={idx} style={{ marginBottom: "12px" }}>
                <button
                  onClick={() => setActiveCourse(activeCourse?.key === `${i}-${idx}` ? null : {
                    key: `${i}-${idx}`,
                    course: c
                  })}
                  style={{
                    background: "transparent",
                    color: "white",
                    border: "1px solid #777",
                    borderRadius: "6px",
                    padding: "6px",
                    cursor: "pointer",
                    width: "100%",
                    textAlign: "left"
                  }}
                >
                  <strong>{c.course}</strong> ({c.credits} credits) — {c.time}
                </button>

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

      {activeCourse && (
        <div
          onClick={() => setActiveCourse(null)}
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.5)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 999
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: "white",
              color: "#111",
              padding: "16px",
              width: "min(700px, 90vw)",
              borderRadius: "8px"
            }}
          >
            <h3 style={{ marginTop: 0 }}>{activeCourse.course.course}</h3>
            <p style={{ marginTop: 0, color: "#333" }}>
              {activeCourse.course.title || "No title available"}
            </p>
            <div style={{ fontSize: "14px", marginBottom: "10px" }}>
              <strong>Description:</strong>{" "}
              {activeCourse.course.description || "No description available."}
            </div>
            <div style={{ fontSize: "14px", marginBottom: "10px" }}>
              <strong>Reason it was recommended:</strong>{" "}
              {activeCourse.course.reasons?.length
                ? activeCourse.course.reasons.join(", ")
                : "No specific recommendation reason available."}
            </div>
            <button onClick={() => setActiveCourse(null)}>Close</button>
          </div>
        </div>
      )}
    </div>
  );
}