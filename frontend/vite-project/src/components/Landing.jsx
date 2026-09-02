import { useEffect, useState } from "react";
import { fetchRoles, uploadResume } from "../api.js";

export default function Landing({ onSessionStart }) {
  const [roles, setRoles] = useState([]);
  const [selectedRole, setSelectedRole] = useState(null);
  const [file, setFile] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchRoles()
      .then((data) => {
        setRoles(data);
        if (data.length > 0) setSelectedRole(data[0].role_id);
      })
      .catch((err) => setError(err.message));
  }, []);

  function handleFileChange(e) {
    const f = e.target.files?.[0];
    if (f) setFile(f);
  }

  function handleDrop(e) {
    e.preventDefault();
    setDragActive(false);
    const f = e.dataTransfer.files?.[0];
    if (f) setFile(f);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!selectedRole || !file) return;

    setSubmitting(true);
    setError(null);
    try {
      const session = await uploadResume(selectedRole, file);
      onSessionStart(session);
    } catch (err) {
      setError(err.message);
      setSubmitting(false);
    }
  }

  const canSubmit = selectedRole && file && !submitting;

  return (
    <>
      <header className="masthead">
        <p className="masthead-eyebrow">Technical screening</p>
        <h1>Role-based candidate interview</h1>
      </header>

      <form className="card" onSubmit={handleSubmit}>
        <div className="field">
          <label>Target role</label>
          <div className="role-grid">
            {roles.map((role) => (
              <label
                key={role.role_id}
                className={`role-option ${selectedRole === role.role_id ? "selected" : ""}`}
              >
                <input
                  type="radio"
                  name="role"
                  value={role.role_id}
                  checked={selectedRole === role.role_id}
                  onChange={() => setSelectedRole(role.role_id)}
                />
                {role.display_name}
              </label>
            ))}
          </div>
        </div>

        <div className="field">
          <label htmlFor="resume-input">Resume</label>
          <div
            className={`dropzone ${dragActive ? "active" : ""}`}
            onDragOver={(e) => {
              e.preventDefault();
              setDragActive(true);
            }}
            onDragLeave={() => setDragActive(false)}
            onDrop={handleDrop}
            onClick={() => document.getElementById("resume-input").click()}
          >
            <input
              id="resume-input"
              type="file"
              accept=".pdf,.txt"
              onChange={handleFileChange}
            />
            {file ? (
              <>
                Ready to upload
                <div className="dropzone-filename">{file.name}</div>
              </>
            ) : (
              "Drop a PDF or text resume here, or click to browse"
            )}
          </div>
        </div>

        <button type="submit" className="btn-primary" disabled={!canSubmit}>
          {submitting ? "Starting session…" : "Start interview"}
        </button>

        {error && <div className="error-banner">{error}</div>}
      </form>

      <p className="helper-text">
        Questions are generated from role-specific reference material and your resume.
      </p>
    </>
  );
}