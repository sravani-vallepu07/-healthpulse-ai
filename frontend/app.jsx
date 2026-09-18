const { useState, useEffect, useRef } = React;

// API Base URL (dynamic for cloud deployment and local dev)
const API_BASE = window.location.origin.startsWith("http") ? `${window.location.origin}/api` : "http://localhost:8000/api";

// Helper for HTTP requests
const api = {
  token: localStorage.getItem("token") || "",
  setToken(t) {
    this.token = t;
    localStorage.setItem("token", t);
  },
  clearToken() {
    this.token = "";
    localStorage.removeItem("token");
  },
  async req(endpoint, method = "GET", body = null) {
    const headers = { "Content-Type": "application/json" };
    if (this.token) headers["Authorization"] = `Bearer ${this.token}`;
    const opts = { method, headers };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(`${API_BASE}${endpoint}`, opts);
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.message || data.detail?.message || "Request failed");
    }
    return data;
  }
};

function App() {
  const [currentUser, setCurrentUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("assistant");
  const [notifications, setNotifications] = useState([]);
  const [showNotifications, setShowNotifications] = useState(false);

  useEffect(() => {
    initAuth();
  }, []);

  const initAuth = async () => {
    const savedToken = localStorage.getItem("token");
    if (savedToken) {
      api.token = savedToken;
      try {
        const user = await api.req("/auth/me");
        setCurrentUser(user);
        loadNotifications();
      } catch (e) {
        console.warn("Session expired");
        api.clearToken();
        setCurrentUser(null);
      }
    }
    setLoading(false);
  };

  const loadNotifications = async () => {
    try {
      const data = await api.req("/audit/notifications");
      setNotifications(data);
    } catch (e) {
      console.error(e);
    }
  };

  const handleLogin = async (email, password) => {
    try {
      const res = await api.req("/auth/login", "POST", { email, password });
      api.setToken(res.access_token);
      await initAuth();
    } catch (e) {
      alert("Login failed: " + e.message);
    }
  };

  const handleQuickSwitch = async (email, password) => {
    await handleLogin(email, password);
  };

  const handleLogout = () => {
    api.clearToken();
    setCurrentUser(null);
  };

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-100">
        <div className="flex items-center space-x-3 text-emerald-700 font-semibold text-lg">
          <i className="fa-solid fa-circle-notch fa-spin text-2xl"></i>
          <span>Loading HealthPulse AI Platform...</span>
        </div>
      </div>
    );
  }

  if (!currentUser) {
    return <AuthScreen onLogin={handleLogin} onQuickSwitch={handleQuickSwitch} />;
  }

  return (
    <div className="flex flex-col min-h-screen">
      {/* Top Demo Persona Switcher */}
      <div className="bg-slate-900 text-slate-300 text-xs px-4 py-2 flex flex-wrap items-center justify-between border-b border-slate-800">
        <div className="flex items-center space-x-2 font-medium">
          <span className="bg-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded font-mono">DEMO BAR</span>
          <span>Switch Persona:</span>
        </div>
        <div className="flex flex-wrap gap-2 items-center">
          <button 
            onClick={() => handleQuickSwitch("platform.admin@healthcare.org", "Admin@123")}
            className="hover:bg-slate-800 px-2 py-1 rounded bg-slate-800/60 border border-slate-700 text-amber-300">
            👑 Platform Admin
          </button>
          <button 
            onClick={() => handleQuickSwitch("admin.abc@hospital.org", "Admin@123")}
            className="hover:bg-slate-800 px-2 py-1 rounded bg-slate-800/60 border border-slate-700 text-sky-300">
            🏥 Hospital Admin (ABC)
          </button>
          <button 
            onClick={() => handleQuickSwitch("dr.anil.rao@hospital.org", "Doctor@123")}
            className="hover:bg-slate-800 px-2 py-1 rounded bg-slate-800/60 border border-slate-700 text-indigo-300">
            🩺 Dr. Anil Rao (Ortho)
          </button>
          <button 
            onClick={() => handleQuickSwitch("ramesh.varma@patient.org", "Patient@123")}
            className="hover:bg-slate-800 px-2 py-1 rounded bg-slate-800/60 border border-slate-700 text-emerald-300">
            👤 Patient (Ramesh)
          </button>
        </div>
      </div>

      {/* Main Header */}
      <header className="bg-white border-b border-slate-200 px-6 py-3 flex items-center justify-between sticky top-0 z-30 shadow-sm">
        <div className="flex items-center space-x-3">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-emerald-600 to-teal-500 flex items-center justify-center text-white text-xl shadow-md shadow-emerald-500/20">
            <i className="fa-solid fa-heart-pulse"></i>
          </div>
          <div>
            <div className="font-bold text-slate-800 text-lg leading-tight flex items-center space-x-2">
              <span>HealthPulse AI</span>
              <span className="text-[11px] font-mono font-medium px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                Multi-Tenant EHR
              </span>
            </div>
            <div className="text-xs text-slate-500">Autonomous Healthcare Intake & Voice Scheduling</div>
          </div>
        </div>

        <div className="flex items-center space-x-4">
          {/* Notifications Dropdown */}
          <div className="relative">
            <button 
              onClick={() => setShowNotifications(!showNotifications)}
              className="relative p-2 text-slate-600 hover:text-emerald-700 hover:bg-slate-100 rounded-lg transition">
              <i className="fa-regular fa-bell text-lg"></i>
              {notifications.filter(n => n.status === "UNREAD").length > 0 && (
                <span className="absolute top-1 right-1 h-2.5 w-2.5 bg-rose-500 rounded-full ring-2 ring-white"></span>
              )}
            </button>
            {showNotifications && (
              <div className="absolute right-0 mt-2 w-80 bg-white border border-slate-200 rounded-xl shadow-xl z-50 p-3">
                <div className="flex justify-between items-center pb-2 border-b border-slate-100 mb-2">
                  <span className="font-semibold text-xs text-slate-700">Notifications</span>
                  <span className="text-[10px] text-slate-400">{notifications.length} alerts</span>
                </div>
                <div className="max-h-64 overflow-y-auto space-y-2">
                  {notifications.length === 0 ? (
                    <div className="text-xs text-slate-400 py-3 text-center">No notifications</div>
                  ) : (
                    notifications.map(n => (
                      <div key={n.id} className="p-2 bg-slate-50 rounded text-xs border border-slate-100">
                        <div className="font-medium text-slate-800">{n.title}</div>
                        <div className="text-slate-600 mt-0.5">{n.message}</div>
                        <div className="text-[10px] text-slate-400 mt-1">{new Date(n.timestamp).toLocaleTimeString()}</div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}
          </div>

          {/* User Profile Pill */}
          <div className="flex items-center space-x-3 bg-slate-100 py-1.5 px-3 rounded-full border border-slate-200">
            <div className="h-7 w-7 rounded-full bg-emerald-600 text-white font-bold flex items-center justify-center text-xs">
              {currentUser.name.charAt(0)}
            </div>
            <div className="text-left">
              <div className="text-xs font-semibold text-slate-800 leading-none">{currentUser.name}</div>
              <div className="text-[10px] font-mono text-emerald-700 uppercase tracking-wide mt-0.5">
                {currentUser.role}
              </div>
            </div>
            <button 
              onClick={handleLogout}
              className="text-slate-400 hover:text-rose-600 ml-2 transition"
              title="Sign Out">
              <i className="fa-solid fa-arrow-right-from-bracket text-xs"></i>
            </button>
          </div>
        </div>
      </header>

      {/* Main Content Area based on User Role */}
      <div className="flex-1 bg-slate-50">
        {currentUser.role === "PATIENT" && (
          <PatientDashboardView 
            user={currentUser} 
            activeTab={activeTab} 
            setActiveTab={setActiveTab} 
            onAppointmentBooked={loadNotifications}
          />
        )}
        {currentUser.role === "DOCTOR" && (
          <DoctorDashboardView user={currentUser} />
        )}
        {currentUser.role === "HOSPITAL_ADMIN" && (
          <HospitalAdminDashboardView user={currentUser} />
        )}
        {currentUser.role === "PLATFORM_ADMIN" && (
          <PlatformAdminDashboardView user={currentUser} />
        )}
      </div>
    </div>
  );
}

// -------------------------------------------------------------
// AUTH SCREEN
// -------------------------------------------------------------
function AuthScreen({ onLogin, onQuickSwitch }) {
  const [email, setEmail] = useState("ramesh.varma@patient.org");
  const [password, setPassword] = useState("Patient@123");

  const submit = (e) => {
    e.preventDefault();
    onLogin(email, password);
  };

  return (
    <div className="min-h-screen bg-slate-100 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center">
        <div className="mx-auto h-14 w-14 rounded-2xl bg-gradient-to-tr from-emerald-600 to-teal-500 flex items-center justify-center text-white text-3xl shadow-lg shadow-emerald-500/30">
          <i className="fa-solid fa-heart-pulse"></i>
        </div>
        <h2 className="mt-4 text-3xl font-extrabold text-slate-900 tracking-tight">HealthPulse AI</h2>
        <p className="mt-1 text-sm text-slate-600">Multi-Hospital Intake, Scheduling & Voice Agent Platform</p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white py-8 px-6 shadow-xl rounded-2xl sm:px-10 border border-slate-200">
          <form className="space-y-4" onSubmit={submit}>
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider">Email Address</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="mt-1 block w-full px-3 py-2 border border-slate-300 rounded-lg text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider">Password</label>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="mt-1 block w-full px-3 py-2 border border-slate-300 rounded-lg text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
              />
            </div>
            <button
              type="submit"
              className="w-full flex justify-center py-2.5 px-4 border border-transparent rounded-lg shadow-md text-sm font-semibold text-white bg-emerald-600 hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-emerald-500 transition">
              Sign In to Platform
            </button>
          </form>

          <div className="mt-6 pt-6 border-t border-slate-200">
            <div className="text-xs font-semibold text-slate-500 mb-3 text-center uppercase tracking-wider">
              1-Click Demo Personas
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <button
                type="button"
                onClick={() => onQuickSwitch("ramesh.varma@patient.org", "Patient@123")}
                className="p-2.5 rounded-lg border border-slate-200 bg-slate-50 hover:bg-emerald-50 hover:border-emerald-300 text-left transition">
                <div className="font-semibold text-slate-800">👤 Patient</div>
                <div className="text-[11px] text-slate-500">Ramesh Varma</div>
              </button>
              <button
                type="button"
                onClick={() => onQuickSwitch("dr.anil.rao@hospital.org", "Doctor@123")}
                className="p-2.5 rounded-lg border border-slate-200 bg-slate-50 hover:bg-indigo-50 hover:border-indigo-300 text-left transition">
                <div className="font-semibold text-slate-800">🩺 Doctor</div>
                <div className="text-[11px] text-slate-500">Dr. Anil Rao (Ortho)</div>
              </button>
              <button
                type="button"
                onClick={() => onQuickSwitch("admin.abc@hospital.org", "Admin@123")}
                className="p-2.5 rounded-lg border border-slate-200 bg-slate-50 hover:bg-sky-50 hover:border-sky-300 text-left transition">
                <div className="font-semibold text-slate-800">🏥 Hospital Admin</div>
                <div className="text-[11px] text-slate-500">ABC Hospital</div>
              </button>
              <button
                type="button"
                onClick={() => onQuickSwitch("platform.admin@healthcare.org", "Admin@123")}
                className="p-2.5 rounded-lg border border-slate-200 bg-slate-50 hover:bg-amber-50 hover:border-amber-300 text-left transition">
                <div className="font-semibold text-slate-800">👑 Platform Admin</div>
                <div className="text-[11px] text-slate-500">Global Controls</div>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// -------------------------------------------------------------
// PATIENT VIEW: AI Voice & Scheduling Assistant
// -------------------------------------------------------------
function PatientDashboardView({ user, activeTab, setActiveTab, onAppointmentBooked }) {
  const [appointments, setAppointments] = useState([]);
  const [questionnaires, setQuestionnaires] = useState([]);
  const [selectedQuestionnaire, setSelectedQuestionnaire] = useState(null);
  const [answers, setAnswers] = useState({});
  const [verificationResult, setVerificationResult] = useState(null);

  useEffect(() => {
    loadAppointments();
    loadQuestionnaires();
  }, []);

  const loadAppointments = async () => {
    try {
      const data = await api.req("/appointments");
      setAppointments(data);
    } catch (e) {
      console.error(e);
    }
  };

  const loadQuestionnaires = async () => {
    try {
      const data = await api.req("/questionnaires");
      setQuestionnaires(data);
    } catch (e) {
      console.error(e);
    }
  };

  const handleOpenQuestionnaire = async (qId, aptId) => {
    try {
      const data = await api.req(`/questionnaires/${qId}`);
      setSelectedQuestionnaire({ ...data, appointment_id: aptId });
      setAnswers({});
    } catch (e) {
      alert("Error loading questionnaire: " + e.message);
    }
  };

  const handleAnswerChange = (qId, val) => {
    setAnswers(prev => ({ ...prev, [qId]: val }));
  };

  const handleSubmitQuestionnaire = async (e) => {
    e.preventDefault();
    try {
      await api.req(`/questionnaires/${selectedQuestionnaire.id}/responses`, "POST", {
        appointment_id: selectedQuestionnaire.appointment_id,
        responses: answers
      });
      alert("Pre-visit questionnaire submitted successfully! Your doctor can now review your intake details.");
      setSelectedQuestionnaire(null);
    } catch (err) {
      alert("Submission error: " + err.message);
    }
  };

  const handleVerifyEHR = async (aptId) => {
    try {
      const res = await api.req(`/appointments/${aptId}/verify`, "POST");
      setVerificationResult(res);
    } catch (e) {
      alert("Verification failed: " + e.message);
    }
  };

  const handleCancelApt = async (aptId) => {
    if (!confirm("Are you sure you want to cancel this appointment?")) return;
    try {
      await api.req(`/appointments/${aptId}/cancel`, "POST", { reason: "Patient cancelled via portal" });
      alert("Appointment cancelled and slot released.");
      loadAppointments();
    } catch (e) {
      alert("Error: " + e.message);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      {/* Navigation tabs */}
      <div className="flex space-x-3 mb-6 border-b border-slate-200 pb-3">
        <button
          onClick={() => setActiveTab("assistant")}
          className={`px-4 py-2 rounded-lg text-sm font-semibold flex items-center space-x-2 transition ${
            activeTab === "assistant"
              ? "bg-emerald-600 text-white shadow-sm"
              : "bg-white text-slate-700 hover:bg-slate-100 border border-slate-200"
          }`}>
          <i className="fa-solid fa-microphone-lines"></i>
          <span>AI Voice & Intake Assistant</span>
        </button>
        <button
          onClick={() => { setActiveTab("appointments"); loadAppointments(); }}
          className={`px-4 py-2 rounded-lg text-sm font-semibold flex items-center space-x-2 transition ${
            activeTab === "appointments"
              ? "bg-emerald-600 text-white shadow-sm"
              : "bg-white text-slate-700 hover:bg-slate-100 border border-slate-200"
          }`}>
          <i className="fa-regular fa-calendar-check"></i>
          <span>My Scheduled Appointments ({appointments.length})</span>
        </button>
      </div>

      {activeTab === "assistant" && (
        <AIVoiceAssistantCard 
          onBookingSuccess={() => { loadAppointments(); onAppointmentBooked(); }}
          onOpenQuestionnaire={handleOpenQuestionnaire}
        />
      )}

      {activeTab === "appointments" && (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <h3 className="text-lg font-bold text-slate-800">My Appointments</h3>
            <button 
              onClick={loadAppointments}
              className="text-xs text-emerald-700 hover:underline flex items-center space-x-1">
              <i className="fa-solid fa-arrows-rotate"></i>
              <span>Refresh</span>
            </button>
          </div>

          {appointments.length === 0 ? (
            <div className="bg-white rounded-xl p-8 text-center border border-slate-200 text-slate-500">
              <i className="fa-regular fa-calendar text-4xl text-slate-300 mb-3"></i>
              <div>No appointments found. Use the AI Assistant to schedule with an approved doctor!</div>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {appointments.map(a => (
                <div key={a.id} className="bg-white rounded-xl p-5 border border-slate-200 shadow-sm relative">
                  <div className="flex justify-between items-start">
                    <div>
                      <span className="text-xs font-mono font-medium text-slate-400">APT-{a.id}</span>
                      <h4 className="font-bold text-slate-800 text-base">{a.doctor_name}</h4>
                      <div className="text-xs text-emerald-700 font-medium">{a.specialty} • {a.hospital_name}</div>
                    </div>
                    <span className={`text-[11px] font-bold px-2.5 py-0.5 rounded-full ${
                      a.status === "CONFIRMED" ? "bg-emerald-100 text-emerald-800" :
                      a.status === "RESCHEDULED" ? "bg-indigo-100 text-indigo-800" :
                      a.status === "CANCELLED" ? "bg-rose-100 text-rose-800" :
                      "bg-amber-100 text-amber-800"
                    }`}>
                      {a.status}
                    </span>
                  </div>

                  <div className="mt-3 py-2 border-y border-slate-100 flex items-center justify-between text-xs text-slate-600">
                    <div className="flex items-center space-x-1.5">
                      <i className="fa-regular fa-calendar text-emerald-600"></i>
                      <span>{a.date}</span>
                    </div>
                    <div className="flex items-center space-x-1.5">
                      <i className="fa-regular fa-clock text-emerald-600"></i>
                      <span>{a.start_time} - {a.end_time}</span>
                    </div>
                    <div className="text-slate-400 font-mono text-[10px]">
                      {a.external_appointment_id || "No External Ref"}
                    </div>
                  </div>

                  <div className="mt-4 flex items-center justify-between">
                    <button
                      onClick={() => handleVerifyEHR(a.id)}
                      className="text-xs text-teal-700 hover:text-teal-900 font-medium flex items-center space-x-1">
                      <i className="fa-solid fa-shield-halved"></i>
                      <span>Verify EHR Record</span>
                    </button>

                    {a.status === "CONFIRMED" && (
                      <div className="space-x-2">
                        <button
                          onClick={() => handleOpenQuestionnaire(1, a.id)}
                          className="text-xs bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200 px-2.5 py-1 rounded font-medium transition">
                          Pre-Visit Form
                        </button>
                        <button
                          onClick={() => handleCancelApt(a.id)}
                          className="text-xs text-rose-600 hover:text-rose-800 font-medium transition">
                          Cancel
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Verification Modal */}
          {verificationResult && (
            <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50">
              <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200">
                <div className="flex justify-between items-center mb-4">
                  <div className="flex items-center space-x-2 text-teal-700 font-bold">
                    <i className="fa-solid fa-circle-check text-xl"></i>
                    <span>Mock EHR Independent Verification</span>
                  </div>
                  <button onClick={() => setVerificationResult(null)} className="text-slate-400 hover:text-slate-600">
                    <i className="fa-solid fa-xmark"></i>
                  </button>
                </div>
                <div className="bg-slate-50 rounded-xl p-4 text-xs font-mono space-y-2 border border-slate-200">
                  <div><strong>Internal Status:</strong> {verificationResult.internal_status}</div>
                  <div><strong>EHR Verified:</strong> {verificationResult.is_verified_in_ehr ? "YES (Record Located)" : "NO"}</div>
                  <div><strong>External ID:</strong> {verificationResult.external_record?.external_id}</div>
                  <div><strong>External Status:</strong> {verificationResult.external_record?.status}</div>
                  <div><strong>Idempotency Key:</strong> {verificationResult.external_record?.idempotency_key}</div>
                </div>
                <button
                  onClick={() => setVerificationResult(null)}
                  className="mt-4 w-full bg-slate-800 text-white text-xs font-semibold py-2 rounded-lg hover:bg-slate-700">
                  Close
                </button>
              </div>
            </div>
          )}

          {/* Pre-Visit Questionnaire Modal */}
          {selectedQuestionnaire && (
            <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50">
              <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200 max-h-[90vh] overflow-y-auto">
                <div className="flex justify-between items-center pb-3 border-b border-slate-200 mb-4">
                  <div>
                    <h3 className="font-bold text-slate-800">{selectedQuestionnaire.name}</h3>
                    <div className="text-xs text-slate-500">For Appointment #{selectedQuestionnaire.appointment_id}</div>
                  </div>
                  <button onClick={() => setSelectedQuestionnaire(null)} className="text-slate-400 hover:text-slate-600">
                    <i className="fa-solid fa-xmark"></i>
                  </button>
                </div>

                <form onSubmit={handleSubmitQuestionnaire} className="space-y-4">
                  {selectedQuestionnaire.questions.map((q) => (
                    <div key={q.id} className="space-y-1">
                      <label className="text-xs font-semibold text-slate-700">
                        {q.question} {q.required && <span className="text-rose-500">*</span>}
                      </label>

                      {q.type === "SINGLE_CHOICE" && (
                        <select
                          required={q.required}
                          value={answers[q.id] || ""}
                          onChange={(e) => handleAnswerChange(q.id, e.target.value)}
                          className="w-full text-xs p-2 border border-slate-300 rounded-lg focus:ring-emerald-500">
                          <option value="">Select an option...</option>
                          {q.options.map(opt => (
                            <option key={opt} value={opt}>{opt}</option>
                          ))}
                        </select>
                      )}

                      {q.type === "YES_NO" && (
                        <div className="flex space-x-4 pt-1 text-xs">
                          <label className="flex items-center space-x-1.5">
                            <input
                              type="radio"
                              name={`q_${q.id}`}
                              value="Yes"
                              checked={answers[q.id] === "Yes"}
                              onChange={() => handleAnswerChange(q.id, "Yes")}
                            />
                            <span>Yes</span>
                          </label>
                          <label className="flex items-center space-x-1.5">
                            <input
                              type="radio"
                              name={`q_${q.id}`}
                              value="No"
                              checked={answers[q.id] === "No"}
                              onChange={() => handleAnswerChange(q.id, "No")}
                            />
                            <span>No</span>
                          </label>
                        </div>
                      )}

                      {q.type === "NUMERIC" && (
                        <input
                          type="number"
                          min="1"
                          max="10"
                          required={q.required}
                          placeholder="e.g. 7"
                          value={answers[q.id] || ""}
                          onChange={(e) => handleAnswerChange(q.id, e.target.value)}
                          className="w-full text-xs p-2 border border-slate-300 rounded-lg focus:ring-emerald-500"
                        />
                      )}

                      {q.type === "SHORT_TEXT" && (
                        <input
                          type="text"
                          required={q.required}
                          placeholder="Describe..."
                          value={answers[q.id] || ""}
                          onChange={(e) => handleAnswerChange(q.id, e.target.value)}
                          className="w-full text-xs p-2 border border-slate-300 rounded-lg focus:ring-emerald-500"
                        />
                      )}
                    </div>
                  ))}

                  <div className="pt-4 flex justify-end space-x-2">
                    <button
                      type="button"
                      onClick={() => setSelectedQuestionnaire(null)}
                      className="px-3 py-1.5 border border-slate-300 text-xs rounded-lg text-slate-700 hover:bg-slate-50">
                      Cancel
                    </button>
                    <button
                      type="submit"
                      className="px-4 py-1.5 bg-emerald-600 text-xs font-semibold text-white rounded-lg hover:bg-emerald-700 shadow-sm">
                      Submit Intake Responses
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// -------------------------------------------------------------
// AI VOICE ASSISTANT COMPONENT
// -------------------------------------------------------------
function AIVoiceAssistantCard({ onBookingSuccess, onOpenQuestionnaire }) {
  const [messages, setMessages] = useState([
    {
      sender: "ai",
      text: "Hello! I am your administrative healthcare scheduling assistant. You can speak or type to discover doctors, check live hospital availability, and book appointments.",
      slots: [],
      appointment: null
    }
  ]);
  const [inputText, setInputText] = useState("");
  const [isListening, setIsListening] = useState(false);
  const [isAiSpeaking, setIsAiSpeaking] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [conversationId, setConversationId] = useState(null);
  const chatEndRef = useRef(null);

  // Web Speech API references
  const recognitionRef = useRef(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isThinking]);

  useEffect(() => {
    // Setup Web Speech Recognition if supported
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      const recognizer = new SpeechRecognition();
      recognizer.continuous = false;
      recognizer.interimResults = false;
      recognizer.lang = "en-US";

      recognizer.onstart = () => setIsListening(true);
      recognizer.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        setIsListening(false);
        handleSend(transcript);
      };
      recognizer.onerror = () => setIsListening(false);
      recognizer.onend = () => setIsListening(false);
      recognitionRef.current = recognizer;
    }
  }, []);

  const speakText = (text) => {
    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.onstart = () => setIsAiSpeaking(true);
      utterance.onend = () => setIsAiSpeaking(false);
      utterance.onerror = () => setIsAiSpeaking(false);
      window.speechSynthesis.speak(utterance);
    }
  };

  const stopSpeaking = () => {
    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
      setIsAiSpeaking(false);
    }
  };

  const toggleListening = () => {
    if (isListening) {
      recognitionRef.current?.stop();
      setIsListening(false);
    } else {
      stopSpeaking();
      try {
        recognitionRef.current?.start();
      } catch (err) {
        console.warn(err);
      }
    }
  };

  const handleSend = async (textToSend) => {
    const msg = textToSend || inputText;
    if (!msg.trim()) return;
    setInputText("");
    stopSpeaking();

    // Add user message to UI
    setMessages(prev => [...prev, { sender: "user", text: msg }]);
    setIsThinking(true);

    try {
      const res = await api.req("/ai/chat", "POST", {
        conversation_id: conversationId,
        message: msg
      });

      setConversationId(res.conversation_id);
      setIsThinking(false);

      setMessages(prev => [...prev, {
        sender: "ai",
        text: res.reply,
        slots: res.slots_suggested || [],
        appointment: res.appointment_data,
        is_escalated: res.is_escalated,
        correlation_id: res.correlation_id
      }]);

      speakText(res.reply);

      if (res.appointment_data) {
        onBookingSuccess();
      }
    } catch (e) {
      setIsThinking(false);
      setMessages(prev => [...prev, { sender: "ai", text: "I encountered an error: " + e.message }]);
    }
  };

  const handleBookSlotClick = (slot) => {
    handleSend(`Book slot at ${slot.start_time}`);
  };

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden flex flex-col h-[700px]">
      {/* Assistant Voice Status Bar */}
      <div className="bg-gradient-to-r from-emerald-700 to-teal-800 text-white p-4 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className={`h-10 w-10 rounded-full flex items-center justify-center transition ${
            isListening ? "bg-rose-500 mic-pulse" :
            isAiSpeaking ? "bg-amber-400 text-slate-900" :
            "bg-emerald-500"
          }`}>
            <i className={`fa-solid ${
              isListening ? "fa-microphone" :
              isAiSpeaking ? "fa-volume-high animate-bounce" :
              "fa-robot"
            } text-lg`}></i>
          </div>
          <div>
            <div className="font-bold text-sm">Autonomous Pre-Visit Intake Agent</div>
            <div className="text-xs text-emerald-200">
              {isListening ? "Listening to your voice..." :
               isAiSpeaking ? "Speaking response..." :
               isThinking ? "Executing capabilities & checking availability..." :
               "Ready • Click microphone or type below"}
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          {isAiSpeaking && (
            <button
              onClick={stopSpeaking}
              className="text-xs bg-slate-900/40 hover:bg-slate-900/60 px-3 py-1 rounded-full border border-white/20 flex items-center space-x-1">
              <i className="fa-solid fa-stop text-[10px]"></i>
              <span>Stop Voice</span>
            </button>
          )}
          <button
            onClick={toggleListening}
            className={`px-4 py-1.5 rounded-full text-xs font-semibold flex items-center space-x-1.5 shadow-sm transition ${
              isListening
                ? "bg-rose-600 hover:bg-rose-700 text-white mic-pulse"
                : "bg-white text-emerald-800 hover:bg-emerald-50"
            }`}>
            <i className="fa-solid fa-microphone"></i>
            <span>{isListening ? "Listening..." : "Speak Voice"}</span>
          </button>
        </div>
      </div>

      {/* Transcript Chat Area */}
      <div className="flex-1 p-4 overflow-y-auto space-y-4 bg-slate-50/50">
        {messages.map((m, idx) => (
          <div key={idx} className={`flex ${m.sender === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[80%] rounded-2xl p-4 shadow-sm text-sm ${
              m.sender === "user"
                ? "bg-emerald-600 text-white rounded-br-none"
                : m.is_escalated
                ? "bg-rose-50 border border-rose-200 text-rose-900 rounded-bl-none"
                : "bg-white border border-slate-200 text-slate-800 rounded-bl-none"
            }`}>
              {m.is_escalated && (
                <div className="flex items-center space-x-1.5 text-rose-700 font-bold text-xs mb-1">
                  <i className="fa-solid fa-triangle-exclamation"></i>
                  <span>CLINICAL SAFETY ESCALATION</span>
                </div>
              )}
              <div className="whitespace-pre-wrap leading-relaxed">{m.text}</div>

              {/* Real Available Slots Cards */}
              {m.slots && m.slots.length > 0 && (
                <div className="mt-3 pt-3 border-t border-slate-100">
                  <div className="text-xs font-semibold text-slate-600 mb-2">Available Time Slots:</div>
                  <div className="grid grid-cols-2 gap-2">
                    {m.slots.map((s, sIdx) => (
                      <button
                        key={sIdx}
                        onClick={() => handleBookSlotClick(s)}
                        className="p-2.5 rounded-xl border border-emerald-200 bg-emerald-50/60 hover:bg-emerald-100 text-left transition flex items-center justify-between">
                        <div>
                          <div className="font-bold text-emerald-900 text-xs">{s.start_time} - {s.end_time}</div>
                          <div className="text-[10px] text-slate-500">{s.doctor_name}</div>
                        </div>
                        <i className="fa-solid fa-chevron-right text-emerald-600 text-xs"></i>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Confirmed Appointment Card */}
              {m.appointment && (
                <div className="mt-3 p-3 bg-emerald-50 rounded-xl border border-emerald-200 text-xs">
                  <div className="flex items-center space-x-1.5 text-emerald-800 font-bold mb-1">
                    <i className="fa-solid fa-circle-check text-emerald-600"></i>
                    <span>VERIFIED & CONFIRMED IN EHR</span>
                  </div>
                  <div><strong>Doctor:</strong> {m.appointment.doctor_name}</div>
                  <div><strong>Date & Time:</strong> {m.appointment.date} at {m.appointment.start_time}</div>
                  <div><strong>External Ref:</strong> {m.appointment.external_id}</div>
                  <button
                    onClick={() => onOpenQuestionnaire(1, m.appointment.appointment_id)}
                    className="mt-2 w-full bg-emerald-600 text-white font-semibold py-1.5 rounded-lg hover:bg-emerald-700 transition">
                    Fill Pre-Visit Questionnaire
                  </button>
                </div>
              )}

              {m.correlation_id && (
                <div className="mt-1 text-[10px] text-slate-400 font-mono">
                  Trace ID: {m.correlation_id}
                </div>
              )}
            </div>
          </div>
        ))}

        {isThinking && (
          <div className="flex justify-start">
            <div className="bg-white border border-slate-200 rounded-2xl rounded-bl-none p-3 shadow-sm flex items-center space-x-2 text-slate-500 text-xs">
              <i className="fa-solid fa-circle-notch fa-spin text-emerald-600"></i>
              <span>Agent coordinating with scheduling & EHR...</span>
            </div>
          </div>
        )}
        <div ref={chatEndRef}></div>
      </div>

      {/* Suggested Quick Prompts */}
      <div className="px-4 py-2 bg-slate-100/60 border-t border-slate-200 flex flex-wrap gap-2 text-xs">
        <span className="text-slate-400 text-[11px] self-center">Try:</span>
        <button
          onClick={() => handleSend("I need an orthopedic appointment this week")}
          className="bg-white border border-slate-200 hover:border-emerald-400 px-2.5 py-1 rounded-full text-slate-700">
          "I need an orthopedic appointment this week"
        </button>
        <button
          onClick={() => handleSend("Actually, make that Friday")}
          className="bg-white border border-slate-200 hover:border-emerald-400 px-2.5 py-1 rounded-full text-slate-700">
          "Actually, make that Friday"
        </button>
        <button
          onClick={() => handleSend("I have sharp chest discomfort")}
          className="bg-white border border-rose-200 hover:border-rose-400 px-2.5 py-1 rounded-full text-rose-700">
          "I have sharp chest discomfort" (Safety check)
        </button>
      </div>

      {/* Text Input Footer */}
      <div className="p-3 bg-white border-t border-slate-200 flex items-center space-x-2">
        <input
          type="text"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          placeholder="Type or click Speak Voice above..."
          className="flex-1 text-sm border border-slate-300 rounded-xl px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-emerald-500"
        />
        <button
          onClick={() => handleSend()}
          className="bg-emerald-600 hover:bg-emerald-700 text-white px-5 py-2.5 rounded-xl font-semibold text-sm shadow-sm transition">
          <i className="fa-solid fa-paper-plane"></i>
        </button>
      </div>
    </div>
  );
}

// -------------------------------------------------------------
// DOCTOR DASHBOARD VIEW
// -------------------------------------------------------------
function DoctorDashboardView({ user }) {
  const [appointments, setAppointments] = useState([]);
  const [selectedAptResponses, setSelectedAptResponses] = useState(null);

  useEffect(() => {
    loadDoctorAppointments();
  }, []);

  const loadDoctorAppointments = async () => {
    try {
      const data = await api.req("/appointments");
      setAppointments(data);
    } catch (e) {
      console.error(e);
    }
  };

  const viewPatientResponses = async (aptId) => {
    try {
      const data = await api.req(`/questionnaires/responses/${aptId}`);
      setSelectedAptResponses({ aptId, data });
    } catch (e) {
      alert("Error: " + e.message);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-xl font-bold text-slate-800">Doctor Clinical & Intake Schedule</h2>
          <p className="text-xs text-slate-500">View upcoming patient bookings and pre-visit assessment questionnaires</p>
        </div>
        <button
          onClick={loadDoctorAppointments}
          className="text-xs bg-white border border-slate-200 px-3 py-1.5 rounded-lg font-medium text-slate-700 hover:bg-slate-50">
          <i className="fa-solid fa-arrows-rotate mr-1"></i> Refresh Schedule
        </button>
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="p-4 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
          <span className="font-semibold text-xs text-slate-700 uppercase tracking-wider">Scheduled Patients</span>
          <span className="text-xs text-slate-500 font-mono">{appointments.length} Total</span>
        </div>

        <div className="divide-y divide-slate-100">
          {appointments.length === 0 ? (
            <div className="p-8 text-center text-slate-400 text-xs">No patients scheduled yet.</div>
          ) : (
            appointments.map(a => (
              <div key={a.id} className="p-4 flex flex-col md:flex-row md:items-center justify-between hover:bg-slate-50/60 transition gap-3">
                <div className="flex items-start space-x-3">
                  <div className="h-10 w-10 rounded-full bg-indigo-50 text-indigo-700 flex items-center justify-center font-bold text-sm">
                    {a.patient_name ? a.patient_name.charAt(0) : "P"}
                  </div>
                  <div>
                    <div className="font-bold text-slate-800 text-sm flex items-center space-x-2">
                      <span>{a.patient_name || "Patient"}</span>
                      <span className="text-[10px] font-mono text-slate-400">ID: #{a.patient_id}</span>
                    </div>
                    <div className="text-xs text-slate-500 mt-0.5">
                      <i className="fa-regular fa-calendar text-emerald-600 mr-1"></i> {a.date} at {a.start_time} - {a.end_time}
                    </div>
                    <div className="text-[11px] text-slate-400 mt-0.5">Reason: {a.reason}</div>
                  </div>
                </div>

                <div className="flex items-center space-x-3">
                  <span className={`text-[11px] font-bold px-2.5 py-0.5 rounded-full ${
                    a.status === "CONFIRMED" ? "bg-emerald-100 text-emerald-800" :
                    a.status === "RESCHEDULED" ? "bg-indigo-100 text-indigo-800" :
                    "bg-slate-100 text-slate-700"
                  }`}>
                    {a.status}
                  </span>

                  <button
                    onClick={() => viewPatientResponses(a.id)}
                    className="text-xs bg-indigo-50 text-indigo-700 hover:bg-indigo-100 border border-indigo-200 px-3 py-1.5 rounded-lg font-medium transition flex items-center space-x-1">
                    <i className="fa-solid fa-clipboard-list"></i>
                    <span>Review Intake Form</span>
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Modal for viewing patient intake responses */}
      {selectedAptResponses && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200">
            <div className="flex justify-between items-center pb-3 border-b border-slate-200 mb-4">
              <div>
                <h3 className="font-bold text-slate-800 text-base">Patient Pre-Visit Intake</h3>
                <div className="text-xs text-slate-500">Appointment #{selectedAptResponses.aptId}</div>
              </div>
              <button onClick={() => setSelectedAptResponses(null)} className="text-slate-400 hover:text-slate-600">
                <i className="fa-solid fa-xmark"></i>
              </button>
            </div>

            {selectedAptResponses.data.length === 0 ? (
              <div className="text-xs text-slate-400 py-6 text-center">
                Patient has not yet submitted the pre-visit questionnaire for this appointment.
              </div>
            ) : (
              <div className="space-y-3">
                {selectedAptResponses.data.map(item => (
                  <div key={item.response_id} className="bg-slate-50 p-4 rounded-xl border border-slate-200">
                    <div className="font-semibold text-xs text-slate-700 mb-2">{item.questionnaire_name}</div>
                    <div className="space-y-2 text-xs">
                      {Object.entries(item.responses).map(([k, v]) => (
                        <div key={k} className="flex justify-between border-b border-slate-200/60 pb-1">
                          <span className="text-slate-500 font-medium">Question #{k}:</span>
                          <span className="text-slate-900 font-semibold">{String(v)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}

            <button
              onClick={() => setSelectedAptResponses(null)}
              className="mt-4 w-full bg-slate-800 text-white text-xs font-semibold py-2 rounded-lg hover:bg-slate-700">
              Done Reviewing
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// -------------------------------------------------------------
// HOSPITAL ADMIN DASHBOARD VIEW
// -------------------------------------------------------------
function HospitalAdminDashboardView({ user }) {
  const [hospital, setHospital] = useState(null);
  const [doctors, setDoctors] = useState([]);
  const [showAddDoctor, setShowAddDoctor] = useState(false);
  const [newDoc, setNewDoc] = useState({ name: "", specialty_id: 1, qualifications: "MBBS, MD", experience: 6 });

  useEffect(() => {
    loadHospitalData();
  }, []);

  const loadHospitalData = async () => {
    try {
      if (user.hospital_id) {
        const h = await api.req(`/hospitals/${user.hospital_id}`);
        setHospital(h);
        const docs = await api.req(`/doctors?hospital_id=${user.hospital_id}`);
        setDoctors(docs);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleAddDoctor = async (e) => {
    e.preventDefault();
    try {
      await api.req("/doctors", "POST", {
        hospital_id: user.hospital_id,
        specialty_id: Number(newDoc.specialty_id),
        name: newDoc.name,
        qualifications: newDoc.qualifications,
        experience: Number(newDoc.experience),
        status: "ACTIVE"
      });
      alert("Doctor created and calendar initialized!");
      setShowAddDoctor(false);
      loadHospitalData();
    } catch (err) {
      alert("Error: " + err.message);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
      {hospital && (
        <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm flex justify-between items-center">
          <div>
            <div className="flex items-center space-x-2">
              <h2 className="text-xl font-bold text-slate-800">{hospital.name}</h2>
              <span className={`text-xs font-bold px-2.5 py-0.5 rounded-full ${
                hospital.status === "APPROVED" ? "bg-emerald-100 text-emerald-800" :
                "bg-amber-100 text-amber-800"
              }`}>
                {hospital.status}
              </span>
            </div>
            <div className="text-xs text-slate-500 mt-1">
              {hospital.address}, {hospital.city} • Phone: {hospital.contact_phone}
            </div>
          </div>
          <button
            onClick={() => setShowAddDoctor(true)}
            className="bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold px-4 py-2 rounded-lg shadow-sm transition">
            + Add Doctor
          </button>
        </div>
      )}

      {/* Doctor List */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="p-4 border-b border-slate-100 font-bold text-sm text-slate-800">
          Hospital Medical Staff & Calendars ({doctors.length})
        </div>
        <div className="divide-y divide-slate-100">
          {doctors.map(d => (
            <div key={d.id} className="p-4 flex justify-between items-center">
              <div>
                <div className="font-bold text-slate-800 text-sm">{d.name}</div>
                <div className="text-xs text-emerald-700 font-medium">{d.specialty_name || "General Medicine"}</div>
                <div className="text-xs text-slate-500">{d.qualifications} • {d.experience} yrs exp</div>
              </div>
              <div className="text-right">
                <span className="text-xs font-semibold px-2 py-0.5 bg-emerald-50 text-emerald-700 rounded border border-emerald-200">
                  {d.status}
                </span>
                <div className="text-[10px] text-slate-400 font-mono mt-1">{d.external_provider_id}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {showAddDoctor && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200">
            <h3 className="font-bold text-slate-800 mb-4">Add Doctor to Hospital</h3>
            <form onSubmit={handleAddDoctor} className="space-y-3 text-xs">
              <div>
                <label className="font-semibold text-slate-700">Doctor Full Name</label>
                <input
                  type="text"
                  required
                  placeholder="Dr. Rajesh Gupta"
                  value={newDoc.name}
                  onChange={e => setNewDoc({...newDoc, name: e.target.value})}
                  className="mt-1 w-full p-2 border border-slate-300 rounded-lg"
                />
              </div>
              <div>
                <label className="font-semibold text-slate-700">Specialty</label>
                <select
                  value={newDoc.specialty_id}
                  onChange={e => setNewDoc({...newDoc, specialty_id: e.target.value})}
                  className="mt-1 w-full p-2 border border-slate-300 rounded-lg">
                  <option value="1">Orthopedics</option>
                  <option value="2">General Medicine</option>
                  <option value="3">Dermatology</option>
                </select>
              </div>
              <div>
                <label className="font-semibold text-slate-700">Qualifications</label>
                <input
                  type="text"
                  value={newDoc.qualifications}
                  onChange={e => setNewDoc({...newDoc, qualifications: e.target.value})}
                  className="mt-1 w-full p-2 border border-slate-300 rounded-lg"
                />
              </div>
              <div>
                <label className="font-semibold text-slate-700">Experience (Years)</label>
                <input
                  type="number"
                  value={newDoc.experience}
                  onChange={e => setNewDoc({...newDoc, experience: e.target.value})}
                  className="mt-1 w-full p-2 border border-slate-300 rounded-lg"
                />
              </div>
              <div className="pt-3 flex justify-end space-x-2">
                <button
                  type="button"
                  onClick={() => setShowAddDoctor(false)}
                  className="px-3 py-1.5 border border-slate-300 rounded-lg">
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 bg-emerald-600 text-white rounded-lg font-semibold">
                  Save Doctor
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

// -------------------------------------------------------------
// PLATFORM ADMIN DASHBOARD: Observability & Failure Simulator
// -------------------------------------------------------------
function PlatformAdminDashboardView({ user }) {
  const [opsData, setOpsData] = useState(null);
  const [hospitals, setHospitals] = useState([]);
  const [failureMode, setFailureMode] = useState("NONE");
  const [auditEvents, setAuditEvents] = useState([]);
  const [searchCorrId, setSearchCorrId] = useState("");

  useEffect(() => {
    loadAdminData();
  }, []);

  const loadAdminData = async () => {
    try {
      const ops = await api.req("/ops/overview");
      setOpsData(ops);
      const hList = await api.req("/hospitals");
      setHospitals(hList);
      const fMode = await api.req("/integrations/failure-mode");
      setFailureMode(fMode.current_failure_mode);
      const audits = await api.req("/audit/events");
      setAuditEvents(audits);
    } catch (e) {
      console.error(e);
    }
  };

  const handleUpdateHospitalStatus = async (hId, newStatus) => {
    try {
      await api.req(`/hospitals/${hId}`, "PUT", { status: newStatus });
      alert(`Hospital status updated to ${newStatus}`);
      loadAdminData();
    } catch (e) {
      alert("Error: " + e.message);
    }
  };

  const handleSetFailureMode = async (mode) => {
    try {
      await api.req("/integrations/failure-mode", "POST", { failure_mode: mode });
      setFailureMode(mode);
      alert(`Mock EHR Failure Mode set to: ${mode}`);
    } catch (e) {
      alert("Error: " + e.message);
    }
  };

  const handleSearchAudit = async () => {
    try {
      const endpoint = searchCorrId ? `/audit/events?correlation_id=${searchCorrId}` : "/audit/events";
      const data = await api.req(endpoint);
      setAuditEvents(data);
    } catch (e) {
      alert("Search error: " + e.message);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
      {/* Top Metrics Banner */}
      {opsData && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
            <div className="text-xs text-slate-500 font-semibold uppercase">Hospitals</div>
            <div className="text-2xl font-extrabold text-slate-800 mt-1">{opsData.metrics.hospitals}</div>
          </div>
          <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
            <div className="text-xs text-slate-500 font-semibold uppercase">Doctors</div>
            <div className="text-2xl font-extrabold text-slate-800 mt-1">{opsData.metrics.doctors}</div>
          </div>
          <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
            <div className="text-xs text-slate-500 font-semibold uppercase">Total Appointments</div>
            <div className="text-2xl font-extrabold text-emerald-600 mt-1">{opsData.metrics.appointments}</div>
          </div>
          <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
            <div className="text-xs text-slate-500 font-semibold uppercase">AI Capabilities Executed</div>
            <div className="text-2xl font-extrabold text-indigo-600 mt-1">{opsData.metrics.capability_executions}</div>
          </div>
          <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
            <div className="text-xs text-slate-500 font-semibold uppercase">Reconciliations</div>
            <div className="text-2xl font-extrabold text-amber-600 mt-1">{opsData.metrics.pending_reconciliations}</div>
          </div>
        </div>
      )}

      {/* SECTION 21: MOCK EHR FAILURE SIMULATOR CONTROL */}
      <div className="bg-gradient-to-r from-slate-900 to-slate-800 text-white rounded-2xl p-6 shadow-md">
        <div className="flex justify-between items-start">
          <div>
            <div className="flex items-center space-x-2">
              <span className="h-3 w-3 rounded-full bg-emerald-400 animate-ping"></span>
              <h3 className="font-bold text-base">EHR Failure Injection & Unknown Outcome Simulator</h3>
            </div>
            <p className="text-xs text-slate-400 mt-1 max-w-2xl">
              Simulate gateway network timeouts during booking. The backend will register an UNKNOWN outcome,
              perform independent external state verification, and safely synchronize to CONFIRMED without duplicate creation.
            </p>
          </div>
          <span className="text-xs font-mono font-semibold px-3 py-1 rounded bg-slate-800 border border-slate-700 text-amber-300">
            Active Mode: {failureMode}
          </span>
        </div>

        <div className="mt-4 pt-4 border-t border-slate-700/60 flex flex-wrap gap-2 text-xs">
          <button
            onClick={() => handleSetFailureMode("NONE")}
            className={`px-3 py-1.5 rounded-lg font-medium transition ${
              failureMode === "NONE" ? "bg-emerald-600 text-white" : "bg-slate-800 hover:bg-slate-700 text-slate-300"
            }`}>
            NONE (Normal Operation)
          </button>
          <button
            onClick={() => handleSetFailureMode("TIMEOUT")}
            className={`px-3 py-1.5 rounded-lg font-medium transition ${
              failureMode === "TIMEOUT" ? "bg-rose-600 text-white" : "bg-slate-800 hover:bg-slate-700 text-rose-300"
            }`}>
            ⚡ TIMEOUT (Unknown Outcome Test)
          </button>
          <button
            onClick={() => handleSetFailureMode("NETWORK_ERROR")}
            className={`px-3 py-1.5 rounded-lg font-medium transition ${
              failureMode === "NETWORK_ERROR" ? "bg-amber-600 text-white" : "bg-slate-800 hover:bg-slate-700 text-amber-300"
            }`}>
            NETWORK_ERROR
          </button>
          <button
            onClick={() => handleSetFailureMode("SLOT_CONFLICT")}
            className={`px-3 py-1.5 rounded-lg font-medium transition ${
              failureMode === "SLOT_CONFLICT" ? "bg-purple-600 text-white" : "bg-slate-800 hover:bg-slate-700 text-purple-300"
            }`}>
            SLOT_CONFLICT
          </button>
        </div>
      </div>

      {/* Hospital Lifecycle Review Queue */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="p-4 border-b border-slate-100 font-bold text-sm text-slate-800">
          Hospital Application & Lifecycle Approvals
        </div>
        <div className="divide-y divide-slate-100">
          {hospitals.map(h => (
            <div key={h.id} className="p-4 flex justify-between items-center">
              <div>
                <div className="font-bold text-slate-800 text-sm">{h.name}</div>
                <div className="text-xs text-slate-500">{h.address}, {h.city}</div>
              </div>
              <div className="flex items-center space-x-3">
                <span className={`text-xs font-semibold px-2.5 py-0.5 rounded-full ${
                  h.status === "APPROVED" ? "bg-emerald-100 text-emerald-800" :
                  h.status === "UNDER_REVIEW" ? "bg-amber-100 text-amber-800" :
                  "bg-slate-100 text-slate-700"
                }`}>
                  {h.status}
                </span>

                {h.status !== "APPROVED" && (
                  <button
                    onClick={() => handleUpdateHospitalStatus(h.id, "APPROVED")}
                    className="text-xs bg-emerald-600 hover:bg-emerald-700 text-white px-3 py-1 rounded font-medium shadow-sm transition">
                    Approve Hospital
                  </button>
                )}
                {h.status === "APPROVED" && (
                  <button
                    onClick={() => handleUpdateHospitalStatus(h.id, "SUSPENDED")}
                    className="text-xs bg-rose-50 text-rose-600 hover:bg-rose-100 px-3 py-1 rounded font-medium border border-rose-200 transition">
                    Suspend
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Audit Trail & Correlation ID Explorer */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="p-4 border-b border-slate-100 flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div>
            <div className="font-bold text-sm text-slate-800">Operational Trace & Audit Trail</div>
            <div className="text-xs text-slate-500">Searchable end-to-end execution records with correlation IDs</div>
          </div>
          <div className="flex items-center space-x-2">
            <input
              type="text"
              placeholder="Search Correlation ID (e.g. BOOK-)"
              value={searchCorrId}
              onChange={e => setSearchCorrId(e.target.value)}
              className="text-xs border border-slate-300 rounded-lg px-3 py-1.5 focus:ring-emerald-500"
            />
            <button
              onClick={handleSearchAudit}
              className="bg-slate-800 text-white text-xs font-semibold px-3 py-1.5 rounded-lg hover:bg-slate-700">
              Filter
            </button>
          </div>
        </div>

        <div className="max-h-80 overflow-y-auto divide-y divide-slate-100 text-xs">
          {auditEvents.map(a => (
            <div key={a.id} className="p-3 flex items-center justify-between hover:bg-slate-50/60">
              <div className="flex items-center space-x-3">
                <span className="font-mono text-[10px] text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded">
                  {a.correlation_id}
                </span>
                <div>
                  <span className="font-bold text-slate-800">{a.event_type}</span>
                  <span className="text-slate-500 ml-2">by {a.actor} ({a.role})</span>
                </div>
              </div>
              <div className="text-[11px] text-slate-400 font-mono">
                {new Date(a.timestamp).toLocaleTimeString()}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
