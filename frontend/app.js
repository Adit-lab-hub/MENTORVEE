// API Base Endpoint config
const API_URL = `http://${window.location.hostname}:8000/api/v1`;
const WS_URL = `ws://${window.location.hostname}:8000/api/v1/ws/telemetry`;

// In-Memory state
let activeProcesses = [
    { id: "P1", burst: 4.0, arrival: 0.0, priority: 2, pages: [1, 2, 3] },
    { id: "P2", burst: 2.5, arrival: 1.0, priority: 1, pages: [2, 1, 4] },
    { id: "P3", burst: 5.0, arrival: 2.0, priority: 3, pages: [3, 2, 1] }
];

let activeLocks = [];
let waitQueue = [];
let wsClient = null;

// Telemetry visual states
let targetCpu = 10, curCpu = 10;
let targetMem = 20, curMem = 20;
let targetLat = 2, curLat = 2;

// Secure Session State
let currentUser = null;
let currentClasses = [];
let activeResetToken = "";
let activeLabKey = "";

// Default grading presets
const presets = {
    thrashing_lab: {
        title: "Memory Thrashing Investigation",
        description: "Configure process virtual page requests sequence to saturate physical memory frames. Check replacement policies LRU and FIFO.",
        assertions: [
            { metric: "page_fault_rate", desc: "Page Fault Rate must exceed 60% (>0.6)" },
            { metric: "is_thrashing", desc: "System must enter Thrashing state == True" }
        ],
        config: { ram_size_mb: 8, page_replacement_policy: "FIFO" },
        scenarios: [
            { process_id: "P1", burst_time: 4.0, arrival_time: 0, memory_pages: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] }
        ]
    },
    scheduling_overhead_lab: {
        title: "CPU Quantum Overhead Optimization",
        description: "Analyze how context switch overhead costs affect average turnaround times in Round Robin algorithms.",
        assertions: [
            { metric: "average_waiting_time", desc: "Average Wait Time must be under 15ms" },
            { metric: "average_turnaround_time", desc: "Average Turnaround Time must be under 20ms" }
        ],
        config: { algorithm: "Round Robin", quantum: 1.0, context_switch_overhead: 0.8 },
        scenarios: [
            { process_id: "P1", burst_time: 3.0, arrival_time: 0 },
            { process_id: "P2", burst_time: 4.0, arrival_time: 0.5 }
        ]
    },
    deadlock_lab: {
        title: "Transaction Deadlock Cycles",
        description: "Trace transaction row acquisitions. Students are expected to configure a deadlock state manually.",
        assertions: [
            { metric: "deadlocks", desc: "Deadlock Wait-For cycle graph must contain at least 1 cycle" }
        ],
        config: { pool_size: 5 },
        scenarios: []
    }
};

// Initialize
document.addEventListener("DOMContentLoaded", () => {
    initTabs();
    initProcessTable();
    initTelemetryDials();
    
    // Bind Event Listeners
    document.getElementById("add-proc-btn").addEventListener("click", addProcessRow);
    document.getElementById("run-os-btn").addEventListener("click", runOSSimulation);
    document.getElementById("run-dbms-btn").addEventListener("click", runDBMSSimulation);
    document.getElementById("ws-toggle-btn").addEventListener("click", toggleWebSocket);
    
    // Concurrency Lock manager events
    document.getElementById("lock-acquire-btn").addEventListener("click", acquireLock);
    document.getElementById("lock-release-btn").addEventListener("click", releaseLock);
    document.getElementById("lock-clear-btn").addEventListener("click", clearLockManager);
    
    // Faculty lab presets
    document.getElementById("lab-preset-select").addEventListener("change", selectLabPreset);
    document.getElementById("lab-submit-btn").addEventListener("click", submitLabPreset);
    
    // Chaos trigger bindings
    document.querySelectorAll(".chaos-pill").forEach(btn => {
        btn.addEventListener("click", () => triggerChaos(btn.dataset.chaos));
    });
    document.getElementById("chaos-reset-btn").addEventListener("click", resetChaos);

    // Auth screen switch toggles
    document.getElementById("to-signup-btn").addEventListener("click", (e) => { e.preventDefault(); switchAuthForm("signup"); });
    document.getElementById("to-login-btn").addEventListener("click", (e) => { e.preventDefault(); switchAuthForm("login"); });
    document.getElementById("to-forgot-btn").addEventListener("click", (e) => { e.preventDefault(); switchAuthForm("forgot"); });
    document.getElementById("forgot-back-to-login-btn").addEventListener("click", (e) => { e.preventDefault(); switchAuthForm("login"); });
    document.getElementById("signup-role").addEventListener("change", toggleSignupConditionalFields);
    
    // Auth actions submit bindings
    document.getElementById("login-submit-btn").addEventListener("click", handleLogin);
    document.getElementById("signup-submit-btn").addEventListener("click", handleSignup);
    document.getElementById("forgot-submit-btn").addEventListener("click", handleForgotPassword);
    document.getElementById("reset-submit-btn").addEventListener("click", handleResetPassword);
    document.getElementById("logout-btn").addEventListener("click", handleLogout);

    // Teacher Panel events
    document.getElementById("teacher-content-type").addEventListener("change", toggleTeacherContentFields);
    document.getElementById("teacher-lab-system").addEventListener("change", toggleTeacherLabFields);
    document.getElementById("teacher-publish-btn").addEventListener("click", handleTeacherPublish);

    // Admin Panel events
    document.getElementById("admin-sub-codes").addEventListener("click", () => switchAdminTab("codes"));
    document.getElementById("admin-sub-users").addEventListener("click", () => switchAdminTab("users"));
    document.getElementById("admin-sub-classes").addEventListener("click", () => switchAdminTab("classes"));
    document.getElementById("admin-sub-logs").addEventListener("click", () => switchAdminTab("logs"));
    document.getElementById("admin-code-generate-btn").addEventListener("click", handleAdminGenerateCode);
    document.getElementById("admin-class-create-btn").addEventListener("click", handleAdminCreateClass);

    // Check query params for forgot password recovery token
    const urlParams = new URLSearchParams(window.location.search);
    const recoveryToken = urlParams.get("token");
    if (recoveryToken) {
        activeResetToken = recoveryToken;
        switchAuthForm("reset");
        document.getElementById("auth-overlay").classList.remove("hidden");
    } else {
        // Run session check on start
        checkSession();
    }
});

// ----------------------------------------------------
// Secure Session Authentication Management
// ----------------------------------------------------
async function checkSession() {
    try {
        const res = await fetch(`${API_URL}/auth/me`, { credentials: "include" });
        if (res.ok) {
            currentUser = await res.json();
            document.getElementById("auth-overlay").classList.add("hidden");
            
            // Populate user profile info in sidebar
            document.getElementById("user-profile-section").classList.remove("hidden");
            document.getElementById("user-email-text").innerText = currentUser.email;
            
            const badge = document.getElementById("user-role-badge");
            badge.innerText = currentUser.role;
            badge.className = `badge badge-${currentUser.role}`;

            // Adjust navigation tabs visibilities based on roles
            document.getElementById("nav-student-btn").classList.add("hidden");
            document.getElementById("nav-teacher-btn").classList.add("hidden");
            document.getElementById("nav-admin-btn").classList.add("hidden");

            if (currentUser.role === "student") {
                document.getElementById("nav-student-btn").classList.remove("hidden");
                loadStudentContent();
            } else if (currentUser.role === "teacher") {
                document.getElementById("nav-teacher-btn").classList.remove("hidden");
                loadTeacherDashboard();
            } else if (currentUser.role === "admin") {
                document.getElementById("nav-admin-btn").classList.remove("hidden");
                loadAdminDashboard();
            }

            // Autoconnect telemetry websocket securely
            if (!wsClient) connectWebSocket();
        } else {
            // Unauthenticated
            currentUser = null;
            document.getElementById("auth-overlay").classList.remove("hidden");
            document.getElementById("user-profile-section").classList.add("hidden");
            if (wsClient) wsClient.close();
            
            // Pre-fill and lock invite link if present
            const urlParams = new URLSearchParams(window.location.search);
            const inviteCode = urlParams.get("invite");
            const inviteEmail = urlParams.get("email");
            if (inviteCode && inviteEmail) {
                switchAuthForm("signup");
                document.getElementById("signup-role").value = "teacher";
                toggleSignupConditionalFields();
                const signupEmail = document.getElementById("signup-email");
                signupEmail.value = inviteEmail;
                signupEmail.disabled = true;
                document.getElementById("signup-invite-code").value = inviteCode;
            } else {
                switchAuthForm("login");
            }
            
            // Preload classes list for signup dropdown
            loadClassesForSignup();
        }
    } catch (e) {
        console.error("Session check failed:", e);
    }
}

function switchAuthForm(formId) {
    document.querySelectorAll(".auth-form").forEach(f => f.classList.add("hidden"));
    document.getElementById(`${formId}-form-div`).classList.remove("hidden");
    const statusMsg = document.getElementById("auth-status-message");
    statusMsg.classList.add("hidden");
}

function toggleSignupConditionalFields() {
    const role = document.getElementById("signup-role").value;
    const studentDiv = document.getElementById("signup-student-class-div");
    const teacherDiv = document.getElementById("signup-teacher-code-div");
    
    if (role === "student") {
        studentDiv.classList.remove("hidden");
        teacherDiv.classList.add("hidden");
    } else {
        studentDiv.classList.add("hidden");
        teacherDiv.classList.remove("hidden");
    }
}

async function loadClassesForSignup() {
    try {
        const res = await fetch(`${API_URL}/auth/classes`);
        if (res.ok) {
            currentClasses = await res.json();
            const select = document.getElementById("signup-class-id");
            select.innerHTML = "";
            currentClasses.forEach(c => {
                const opt = document.createElement("option");
                opt.value = c.id;
                opt.innerText = `${c.name} (${c.code})`;
                select.appendChild(opt);
            });
        }
    } catch (e) {
        console.error("Could not load classes:", e);
    }
}

function showAuthMessage(text, isError = false) {
    const el = document.getElementById("auth-status-message");
    el.innerHTML = text;
    el.className = `auth-msg ${isError ? "error" : "success"}`;
    el.classList.remove("hidden");
}

async function handleLogin() {
    const email = document.getElementById("login-email").value;
    const password = document.getElementById("login-password").value;
    if (!email || !password) return showAuthMessage("Email and password are required", true);
    
    try {
        const res = await fetch(`${API_URL}/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password }),
            credentials: "include"
        });
        const data = await res.json();
        if (res.ok) {
            checkSession();
        } else {
            showAuthMessage(data.detail || "Authentication failed", true);
        }
    } catch (e) {
        showAuthMessage("Connection error to server", true);
    }
}

async function handleSignup() {
    const email = document.getElementById("signup-email").value;
    const password = document.getElementById("signup-password").value;
    const confirm = document.getElementById("signup-confirm-password").value;
    const role = document.getElementById("signup-role").value;
    
    if (password !== confirm) return showAuthMessage("Passwords do not match", true);
    
    const payload = { email, password, role };
    if (role === "student") {
        payload.class_id = parseInt(document.getElementById("signup-class-id").value);
    } else {
        payload.invite_code = document.getElementById("signup-invite-code").value;
    }
    
    try {
        const res = await fetch(`${API_URL}/auth/signup`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (res.ok) {
            let msg = data.message;
            if (data.verification_link) {
                // Return a simulation helper button so user can click to mock verify email!
                msg += `<br/><br/><a href="${data.verification_link}" class="btn-sm" style="display:inline-block; margin-top:0.5rem; text-decoration:none; background:var(--accent-green); color:#000; font-weight:bold;">[SIMULATION] Click to verify email address</a>`;
            }
            const el = document.getElementById("auth-status-message");
            el.innerHTML = msg;
            el.className = "auth-msg success";
            el.classList.remove("hidden");
        } else {
            showAuthMessage(data.detail || "Registration failed", true);
        }
    } catch (e) {
        showAuthMessage("Connection error to server", true);
    }
}

async function handleForgotPassword() {
    const email = document.getElementById("forgot-email").value;
    if (!email) return showAuthMessage("Email address is required", true);
    
    try {
        const res = await fetch(`${API_URL}/auth/forgot-password`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email })
        });
        const data = await res.json();
        if (res.ok) {
            let msg = data.message;
            if (data.reset_link) {
                msg += `<br/><br/><a href="${data.reset_link}" class="btn-sm" style="display:inline-block; margin-top:0.5rem; text-decoration:none; background:var(--accent-cyan); color:#000; font-weight:bold;">[SIMULATION] Click to reset password</a>`;
            }
            const el = document.getElementById("auth-status-message");
            el.innerHTML = msg;
            el.className = "auth-msg success";
            el.classList.remove("hidden");
        } else {
            showAuthMessage(data.detail || "Request failed", true);
        }
    } catch (e) {
        showAuthMessage("Connection error", true);
    }
}

async function handleResetPassword() {
    const password = document.getElementById("reset-password").value;
    const confirm = document.getElementById("reset-confirm-password").value;
    if (password !== confirm) return showAuthMessage("Passwords do not match", true);
    
    try {
        const res = await fetch(`${API_URL}/auth/reset-password`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ token: activeResetToken, new_password: password })
        });
        const data = await res.json();
        if (res.ok) {
            showAuthMessage("Password changed successfully. Redirecting to login...", false);
            setTimeout(() => {
                window.history.replaceState({}, document.title, window.location.pathname); // clear query string
                switchAuthForm("login");
            }, 2000);
        } else {
            showAuthMessage(data.detail || "Password reset failed", true);
        }
    } catch (e) {
        showAuthMessage("Connection error", true);
    }
}

async function handleLogout() {
    try {
        await fetch(`${API_URL}/auth/logout`, { method: "POST", credentials: "include" });
        currentUser = null;
        checkSession();
    } catch (e) {
        console.error("Logout failed:", e);
    }
}

// ----------------------------------------------------
// Sidebar navigation tabs toggles
// ----------------------------------------------------
function initTabs() {
    const navButtons = document.querySelectorAll(".nav-btn");
    const contents = document.querySelectorAll(".tab-content");
    const visContents = document.querySelectorAll(".vis-content");

    navButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            navButtons.forEach(b => b.classList.remove("active"));
            contents.forEach(c => c.classList.add("hidden"));
            visContents.forEach(v => v.classList.add("hidden"));

            btn.classList.add("active");
            const tabId = btn.dataset.tab;
            document.getElementById(tabId).classList.remove("hidden");
            
            if (tabId === "os-tab") {
                document.getElementById("os-vis").classList.remove("hidden");
                document.getElementById("tab-title").innerText = "OS Simulation Sandbox";
                document.getElementById("tab-subtitle").innerText = "Deterministic process scheduling, context switches, & virtual page tables";
            } else if (tabId === "dbms-tab") {
                document.getElementById("dbms-vis").classList.remove("hidden");
                document.getElementById("tab-title").innerText = "DBMS Simulation Sandbox";
                document.getElementById("tab-subtitle").innerText = "Disk B-Tree access vs full tables, sequential read metrics";
            } else if (tabId === "concurrency-tab") {
                document.getElementById("concurrency-vis").classList.remove("hidden");
                document.getElementById("tab-title").innerText = "Concurrency & Lock Engine";
                document.getElementById("tab-subtitle").innerText = "Trace exclusive and shared row lock contentions and cycle deadlock detection";
            } else if (tabId === "lab-tab") {
                document.getElementById("lab-vis").classList.remove("hidden");
                document.getElementById("tab-title").innerText = "Faculty Lab Configurations";
                document.getElementById("tab-subtitle").innerText = "Run grading test suites against user-defined resource parameters";
            } else if (tabId === "student-content-tab") {
                document.getElementById("tab-title").innerText = "Class Content Desk";
                document.getElementById("tab-subtitle").innerText = "Access course files and test presets shared by your teacher";
                loadStudentContent();
            } else if (tabId === "teacher-tab") {
                document.getElementById("tab-title").innerText = "Teacher Workspace";
                document.getElementById("tab-subtitle").innerText = "Publish files or configure dynamic sandbox labs for students";
                loadTeacherDashboard();
            } else if (tabId === "admin-tab") {
                document.getElementById("tab-title").innerText = "Administration Console";
                document.getElementById("tab-subtitle").innerText = "Audit logs, generate teacher codes, and manage user accounts";
                loadAdminDashboard();
            }
        });
    });
}

// ----------------------------------------------------
// Student Scoped Content Loading and Presets Action
// ----------------------------------------------------
async function loadStudentContent() {
    try {
        const res = await fetch(`${API_URL}/content`, { credentials: "include" });
        if (!res.ok) return;
        const contents = await res.json();
        
        // Find enrolled class name
        if (currentUser && currentUser.role === "student") {
            const osClass = currentClasses.find(c => c.code === "OS");
            const dbmsClass = currentClasses.find(c => c.code === "DBMS");
            let nameStr = "";
            if (osClass && dbmsClass) {
                nameStr = `${osClass.name} (${osClass.code}) & ${dbmsClass.name} (${dbmsClass.code})`;
            } else {
                nameStr = "Operating Systems (OS) & Database Management Systems (DBMS)";
            }
            document.getElementById("student-class-name").innerText = nameStr;
        } else if (currentUser && currentUser.class_id) {
            const classObj = currentClasses.find(c => c.id === currentUser.class_id);
            document.getElementById("student-class-name").innerText = classObj ? `${classObj.name} (${classObj.code})` : "General";
        }
        
        const list = document.getElementById("student-content-list");
        list.innerHTML = "";
        
        if (contents.length === 0) {
            list.innerHTML = `<p class="table-empty">No content or labs posted for your class yet.</p>`;
            return;
        }
        
        contents.forEach(c => {
            const card = document.createElement("div");
            card.className = "content-card card";
            
            let downloadBtn = "";
            if (c.has_file) {
                downloadBtn = `<a href="${API_URL}/content/${c.id}/download" class="btn-sm" style="text-decoration:none; display:inline-block; margin-top:0.25rem;">💾 Download ${c.file_name}</a>`;
            }
            
            let actionBtn = "";
            if (c.type === "lab") {
                actionBtn = `<button class="btn-primary btn-sm" style="margin-top:0.5rem;" onclick="loadCustomTeacherLab(${c.id}, '${escapeQuote(c.payload)}')">🔬 Load Lab Simulator</button>`;
            }
            
            card.innerHTML = `
                <h4>${c.title}</h4>
                <p>${c.description}</p>
                <div class="content-card-meta">
                    <span>Type: <strong style="color:var(--accent-cyan);">${c.type.toUpperCase()}</strong></span>
                    <span>Date: ${new Date(c.created_at).toLocaleDateString()}</span>
                </div>
                ${downloadBtn}
                ${actionBtn}
            `;
            list.appendChild(card);
        });
    } catch (e) {
        console.error("Student content fetch failed:", e);
    }
}

function escapeQuote(str) {
    return str.replace(/'/g, "\'").replace(/"/g, '&quot;');
}

window.loadCustomTeacherLab = (contentId, payloadStr) => {
    try {
        const p = JSON.parse(payloadStr.replace(/&quot;/g, '"'));
        activeLabKey = contentId.toString();
        
        writeConsole(`Custom Teacher Lab Loaded: ${p.title || "Custom Lab"}. Setting up configuration...`);
        
        if (p.system_type === "OS") {
            document.getElementById("os-ram").value = p.configuration.ram_size_mb || 16;
            document.getElementById("os-policy").value = p.configuration.page_replacement_policy || "LRU";
            document.getElementById("os-algo").value = p.configuration.algorithm || "Round Robin";
            document.getElementById("os-quantum").value = p.configuration.quantum || 2.0;
            document.getElementById("os-overhead").value = p.configuration.context_switch_overhead || 0.1;
            
            activeProcesses = p.scenarios.map(s => ({
                id: s.process_id,
                burst: s.burst_time,
                arrival: s.arrival_time,
                priority: s.priority,
                pages: s.memory_pages || []
            }));
            renderProcessTable();
            document.querySelector('.nav-btn[data-tab="os-tab"]').click();
        } else {
            document.getElementById("dbms-index").value = p.configuration.index_type || "B-Tree";
            document.getElementById("dbms-storage").value = p.configuration.storage_type || "SSD";
            document.getElementById("dbms-buffer").value = p.configuration.buffer_pool_size || 100;
            document.getElementById("dbms-pool").value = p.configuration.pool_size || 10;
            
            if (p.scenarios && p.scenarios.length > 0) {
                const s = p.scenarios[0];
                document.getElementById("dbms-qtype").value = s.query_type || "point";
                document.getElementById("dbms-rows").value = s.num_records || 100000;
                document.getElementById("dbms-range-pct").value = (s.range_fraction || 0.1) * 100;
                document.getElementById("dbms-concurrent").value = s.concurrent_requests || 1;
            }
            document.querySelector('.nav-btn[data-tab="dbms-tab"]').click();
        }
        
        const panel = document.getElementById("lab-instructions-panel");
        const submitBtn = document.getElementById("lab-submit-btn");
        
        document.getElementById("lab-title-text").innerText = p.title;
        document.getElementById("lab-desc-text").innerText = p.description;
        
        const list = document.getElementById("lab-assertions-list");
        list.innerHTML = "";
        
        p.assertions.forEach(a => {
            const li = document.createElement("li");
            let opDesc = a.operator === "<=" ? "under" : "above";
            li.innerHTML = `<span>⚙️</span> Grading: ${a.metric.replace(/_/g, " ")} must be ${opDesc} ${a.value}`;
            list.appendChild(li);
        });
        
        panel.classList.remove("hidden");
        submitBtn.classList.remove("hidden");
        document.getElementById("lab-preset-select").value = ""; 
        writeConsole(`Custom preset loaded. Navigate to "Faculty Labs" tab to grade your configurations!`);
        
    } catch (e) {
        writeConsole("Failed to load custom lab: " + e.message, "error");
    }
};

// ----------------------------------------------------
// Teacher Panel Publishing Wizard Logic
// ----------------------------------------------------
function toggleTeacherContentFields() {
    const type = document.getElementById("teacher-content-type").value;
    if (type === "material") {
        document.getElementById("teacher-material-fields").classList.remove("hidden");
        document.getElementById("teacher-lab-fields").classList.add("hidden");
    } else {
        document.getElementById("teacher-material-fields").classList.add("hidden");
        document.getElementById("teacher-lab-fields").classList.remove("hidden");
    }
}

function toggleTeacherLabFields() {
    const sys = document.getElementById("teacher-lab-system").value;
    if (sys === "OS") {
        document.getElementById("teacher-lab-os-config").classList.remove("hidden");
        document.getElementById("teacher-lab-dbms-config").classList.add("hidden");
    } else {
        document.getElementById("teacher-lab-os-config").classList.add("hidden");
        document.getElementById("teacher-lab-dbms-config").classList.remove("hidden");
    }
}

async function loadTeacherDashboard() {
    try {
        const cres = await fetch(`${API_URL}/auth/classes`);
        if (cres.ok) {
            const classes = await cres.json();
            const select = document.getElementById("teacher-class-select");
            select.innerHTML = "";
            classes.forEach(c => {
                const opt = document.createElement("option");
                opt.value = c.id;
                opt.innerText = `${c.name} (${c.code})`;
                select.appendChild(opt);
            });
        }
        
        const res = await fetch(`${API_URL}/content`, { credentials: "include" });
        if (res.ok) {
            const list = document.getElementById("teacher-content-list");
            list.innerHTML = "";
            const items = await res.json();
            
            if (items.length === 0) {
                list.innerHTML = `<p class="table-empty">You haven't published any material yet.</p>`;
                return;
            }
            
            items.forEach(i => {
                const el = document.createElement("div");
                el.className = "content-card card";
                el.innerHTML = `
                    <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                        <h4>${i.title} (${i.class_name})</h4>
                        <button class="btn-sm" style="color:var(--accent-red); background:rgba(239,68,68,0.1);" onclick="handleDeleteContent(${i.id})">Delete</button>
                    </div>
                    <p style="font-size:0.8rem; color:var(--text-secondary); margin-top:0.25rem;">Type: ${i.type.toUpperCase()}</p>
                `;
                list.appendChild(el);
            });
        }
    } catch (e) {
        console.error("Teacher dashboard loading error:", e);
    }
}

async function handleTeacherPublish() {
    const classId = document.getElementById("teacher-class-select").value;
    const type = document.getElementById("teacher-content-type").value;
    
    const formData = new FormData();
    formData.append("class_id", classId);
    formData.append("content_type", type);
    
    if (type === "material") {
        const title = document.getElementById("material-title").value;
        const desc = document.getElementById("material-desc").value;
        const file = document.getElementById("material-file").files[0];
        
        if (!title) return alert("Title is required");
        formData.append("title", title);
        formData.append("description", desc);
        if (file) {
            formData.append("file", file);
        }
    } else {
        const title = document.getElementById("teacher-lab-title").value;
        const desc = document.getElementById("teacher-lab-desc").value;
        const sys = document.getElementById("teacher-lab-system").value;
        
        if (!title) return alert("Lab title is required");
        
        formData.append("title", title);
        formData.append("description", desc);
        
        const labConfig = {
            system_type: sys,
            configuration: {},
            scenarios: [],
            assertions: []
        };
        
        if (sys === "OS") {
            const ram = parseInt(document.getElementById("teacher-lab-os-ram").value);
            const policy = document.getElementById("teacher-lab-os-policy").value;
            const assertType = document.getElementById("teacher-lab-os-assert").value;
            
            labConfig.configuration = {
                ram_size_mb: ram,
                page_replacement_policy: policy,
                algorithm: "Round Robin",
                quantum: 2.0,
                context_switch_overhead: 0.1
            };
            
            if (assertType === "thrashing") {
                labConfig.scenarios = [
                    { process_id: "P1", burst_time: 10.0, arrival_time: 0.0, priority: 1, memory_pages: [1,2,3,4,5,6,7,8,9,10] }
                ];
                labConfig.assertions = [
                    { metric: "is_thrashing", operator: "==", value: true },
                    { metric: "page_fault_rate", operator: ">=", value: 0.7 }
                ];
            } else {
                labConfig.scenarios = [
                    { process_id: "P1", burst_time: 3.0, arrival_time: 0.0, priority: 1, memory_pages: [1,2] },
                    { process_id: "P2", burst_time: 2.0, arrival_time: 1.0, priority: 2, memory_pages: [2,3] }
                ];
                if (assertType === "no_thrashing") {
                    labConfig.assertions = [
                        { metric: "is_thrashing", operator: "==", value: false },
                        { metric: "page_fault_rate", operator: "<=", value: 0.15 }
                    ];
                } else {
                    labConfig.assertions = [
                        { metric: "average_turnaround_time", operator: "<=", value: 5.0 }
                    ];
                }
            }
        } else {
            const indexType = document.getElementById("teacher-lab-dbms-index").value;
            const storage = document.getElementById("teacher-lab-dbms-storage").value;
            const assertType = document.getElementById("teacher-lab-dbms-assert").value;
            
            labConfig.configuration = {
                index_type: indexType,
                storage_type: storage,
                buffer_pool_size: 100,
                pool_size: 10
            };
            
            labConfig.scenarios = [
                { query_type: "range", num_records: 100000, range_fraction: 0.1, concurrent_requests: 1 }
            ];
            
            if (assertType === "low_latency") {
                labConfig.assertions = [
                    { metric: "average_latency_ms", operator: "<=", value: 5.0 }
                ];
            } else {
                labConfig.assertions = [
                    { metric: "average_latency_ms", operator: ">=", value: 20.0 }
                ];
            }
        }
        
        formData.append("payload", JSON.stringify(labConfig));
    }
    
    try {
        const res = await fetch(`${API_URL}/content`, {
            method: "POST",
            body: formData,
            credentials: "include"
        });
        if (res.ok) {
            alert("Published content successfully!");
            document.getElementById("material-title").value = "";
            document.getElementById("material-desc").value = "";
            document.getElementById("teacher-lab-title").value = "";
            document.getElementById("teacher-lab-desc").value = "";
            loadTeacherDashboard();
        } else {
            const data = await res.json();
            alert("Publishing failed: " + (data.detail || "Unknown error"));
        }
    } catch (e) {
        alert("Publish error: " + e.message);
    }
}

window.handleDeleteContent = async (id) => {
    if (!confirm("Are you sure you want to delete this publication?")) return;
    try {
        const res = await fetch(`${API_URL}/content/${id}`, { method: "DELETE", credentials: "include" });
        if (res.ok) {
            loadTeacherDashboard();
        }
    } catch (e) {
        console.error("Delete failed:", e);
    }
};

// ----------------------------------------------------
// Admin dashboard view management
// ----------------------------------------------------
function switchAdminTab(subId) {
    document.querySelectorAll("[id^='admin-panel-']").forEach(p => p.classList.add("hidden"));
    document.querySelectorAll("[id^='admin-sub-']").forEach(b => b.classList.remove("active"));
    
    document.getElementById(`admin-panel-${subId}`).classList.remove("hidden");
    document.getElementById(`admin-sub-${subId}`).classList.add("active");
}

async function loadAdminDashboard() {
    loadAdminCodes();
    loadAdminUsers();
    loadAdminClasses();
    loadAdminLogs();
}

async function loadAdminCodes() {
    try {
        const res = await fetch(`${API_URL}/admin/invite-codes`, { credentials: "include" });
        if (res.ok) {
            const list = document.querySelector("#admin-codes-table tbody");
            list.innerHTML = "";
            const codes = await res.json();
            if (codes.length === 0) {
                list.innerHTML = `<tr><td colspan="4" class="table-empty">No invite codes generated yet</td></tr>`;
                return;
            }
            codes.forEach(c => {
                const tr = document.createElement("tr");
                tr.innerHTML = `
                    <td>${c.assigned_teacher_email}</td>
                    <td><code style="color:var(--accent-cyan); font-weight:bold;">${c.code}</code></td>
                    <td><span class="badge ${c.status === "unused" ? "badge-student" : "badge-admin"}">${c.status}</span></td>
                    <td>
                        ${c.status === "unused" ? `<button class="btn-sm" style="color:var(--accent-red); background:rgba(239,68,68,0.1);" onclick="handleRevokeCode(${c.id})">Revoke</button>` : "None"}
                    </td>
                `;
                list.appendChild(tr);
            });
        }
    } catch (e) {
        console.error("Load codes failed:", e);
    }
}

async function handleAdminGenerateCode() {
    const email = document.getElementById("admin-code-email").value;
    if (!email) return alert("Email is required");
    try {
        const res = await fetch(`${API_URL}/admin/invite-codes`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email }),
            credentials: "include"
        });
        const data = await res.json();
        if (res.ok) {
            document.getElementById("generated-code-display").classList.remove("hidden");
            document.getElementById("new-code-text").innerText = data.code;
            document.getElementById("new-code-link").value = data.invite_link;
            document.getElementById("admin-code-email").value = "";
            loadAdminCodes();
        } else {
            alert(data.detail || "Generation failed");
        }
    } catch (e) {
        console.error(e);
    }
}

window.handleRevokeCode = async (id) => {
    try {
        await fetch(`${API_URL}/admin/invite-codes/${id}`, { method: "DELETE", credentials: "include" });
        loadAdminCodes();
    } catch (e) {
        console.error(e);
    }
};

async function loadAdminUsers() {
    try {
        const res = await fetch(`${API_URL}/admin/users`, { credentials: "include" });
        const cres = await fetch(`${API_URL}/auth/classes`);
        if (res.ok && cres.ok) {
            const classes = await cres.json();
            const list = document.querySelector("#admin-users-table tbody");
            list.innerHTML = "";
            const users = await res.json();
            
            users.forEach(u => {
                const tr = document.createElement("tr");
                
                let classOptions = `<option value="">-- Unassigned --</option>`;
                classes.forEach(c => {
                    classOptions += `<option value="${c.id}" ${u.class_id === c.id ? "selected" : ""}>${c.name}</option>`;
                });
                const classSelector = `<select style="font-size:0.75rem; padding:0.1rem; width:110px;" onchange="handleAssignClass('${u.id}', this.value)">${classOptions}</select>`;
                
                let actions = "";
                if (u.role === "teacher" && u.status === "pending") {
                    actions += `<button class="btn-sm" style="color:var(--accent-green);" onclick="handleApproveTeacher('${u.id}')">Approve</button> `;
                }
                
                if (u.status === "active") {
                    actions += `<button class="btn-sm" style="color:var(--accent-red);" onclick="handleUpdateUserStatus('${u.id}', 'deactivated')">Deactivate</button>`;
                } else if (u.status === "deactivated") {
                    actions += `<button class="btn-sm" style="color:var(--accent-cyan);" onclick="handleUpdateUserStatus('${u.id}', 'active')">Activate</button>`;
                }
                
                tr.innerHTML = `
                    <td><span style="font-size:0.8rem;">${u.email}</span></td>
                    <td><span class="badge badge-${u.role}">${u.role}</span></td>
                    <td><span style="font-size:0.8rem; font-weight:600;">${u.status}</span></td>
                    <td>
                        <div style="display:flex; flex-direction:column; gap:0.25rem;">
                            ${u.role !== "admin" ? classSelector : ""}
                            <div style="display:flex; gap:0.25rem;">
                                ${actions}
                                <button class="btn-sm" style="color:var(--accent-red); background:rgba(239,68,68,0.1);" onclick="handleDeleteUser('${u.id}')">Del</button>
                            </div>
                        </div>
                    </td>
                `;
                list.appendChild(tr);
            });
        }
    } catch (e) {
        console.error(e);
    }
}

window.handleApproveTeacher = async (id) => {
    try {
        await fetch(`${API_URL}/admin/users/${id}/approve`, { method: "POST", credentials: "include" });
        loadAdminUsers();
    } catch (e) {
        console.error(e);
    }
};

window.handleUpdateUserStatus = async (id, status) => {
    try {
        await fetch(`${API_URL}/admin/users/${id}/status`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ status }),
            credentials: "include"
        });
        loadAdminUsers();
    } catch (e) {
        console.error(e);
    }
};

window.handleDeleteUser = async (id) => {
    if (!confirm("Are you sure you want to permanently delete this user account?")) return;
    try {
        await fetch(`${API_URL}/admin/users/${id}`, { method: "DELETE", credentials: "include" });
        loadAdminUsers();
    } catch (e) {
        console.error(e);
    }
};

window.handleAssignClass = async (userId, classId) => {
    try {
        await fetch(`${API_URL}/admin/users/${userId}/assign-class`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ class_id: classId ? parseInt(classId) : null }),
            credentials: "include"
        });
        loadAdminUsers();
    } catch (e) {
        console.error(e);
    }
};

async function loadAdminClasses() {
    try {
        const res = await fetch(`${API_URL}/auth/classes`);
        if (res.ok) {
            const list = document.getElementById("admin-classes-list");
            list.innerHTML = "";
            const classes = await res.json();
            if (classes.length === 0) {
                list.innerHTML = `<p class="table-empty">No classes created yet</p>`;
                return;
            }
            classes.forEach(c => {
                const li = document.createElement("li");
                li.innerHTML = `<span>📂</span> <strong>${c.code}</strong> - ${c.name}`;
                list.appendChild(li);
            });
        }
    } catch (e) {
        console.error(e);
    }
}

async function handleAdminCreateClass() {
    const name = document.getElementById("admin-class-name").value;
    const code = document.getElementById("admin-class-code").value;
    if (!name || !code) return alert("Class name and code are required");
    
    try {
        const res = await fetch(`${API_URL}/admin/classes`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, code }),
            credentials: "include"
        });
        if (res.ok) {
            document.getElementById("admin-class-name").value = "";
            document.getElementById("admin-class-code").value = "";
            loadAdminClasses();
        } else {
            const data = await res.json();
            alert(data.detail || "Creation failed");
        }
    } catch (e) {
        console.error(e);
    }
}

async function loadAdminLogs() {
    try {
        const res = await fetch(`${API_URL}/admin/audit-logs`, { credentials: "include" });
        if (res.ok) {
            const list = document.querySelector("#admin-logs-table tbody");
            list.innerHTML = "";
            const logs = await res.json();
            if (logs.length === 0) {
                list.innerHTML = `<tr><td colspan="3" class="table-empty">No logs captured</td></tr>`;
                return;
            }
            logs.forEach(l => {
                const tr = document.createElement("tr");
                tr.innerHTML = `
                    <td><strong style="color:var(--accent-blue);">${l.admin_email}</strong></td>
                    <td>${l.action}</td>
                    <td>${new Date(l.timestamp).toLocaleTimeString()}</td>
                `;
                list.appendChild(tr);
            });
        }
    } catch (e) {
        console.error(e);
    }
}

// ----------------------------------------------------
// OS Process Configuration Table Editor
// ----------------------------------------------------
function initProcessTable() {
    renderProcessTable();
}

function renderProcessTable() {
    const tbody = document.querySelector("#process-config-table tbody");
    tbody.innerHTML = "";
    
    activeProcesses.forEach((p, idx) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td><strong style="color:var(--accent-cyan);">${p.id}</strong></td>
            <td><input type="number" value="${p.burst}" step="0.5" min="0.5" style="width:55px;" onchange="updateProcess(${idx}, 'burst', this.value)"></td>
            <td><input type="number" value="${p.arrival}" step="0.5" min="0" style="width:55px;" onchange="updateProcess(${idx}, 'arrival', this.value)"></td>
            <td><input type="number" value="${p.priority}" min="1" style="width:50px;" onchange="updateProcess(${idx}, 'priority', this.value)"></td>
            <td><input type="text" value="${p.pages.join(',')}" placeholder="e.g. 1,2,3" style="width:90px;" onchange="updateProcessPages(${idx}, this.value)"></td>
            <td><button class="btn-sm" style="background:rgba(239,68,68,0.1); border-color:rgba(239,68,68,0.3); color:var(--accent-red);" onclick="removeProcess(${idx})">Del</button></td>
        `;
        tbody.appendChild(tr);
    });
}

window.updateProcess = (idx, field, val) => {
    activeProcesses[idx][field] = parseFloat(val) || 1;
};

window.updateProcessPages = (idx, val) => {
    activeProcesses[idx].pages = val.split(",").map(n => parseInt(n.trim()) || 0).filter(n => n > 0);
};

window.removeProcess = (idx) => {
    activeProcesses.splice(idx, 1);
    renderProcessTable();
};

function addProcessRow() {
    const newId = "P" + (activeProcesses.length + 1);
    activeProcesses.push({
        id: newId,
        burst: 3.0,
        arrival: 0.0,
        priority: 1,
        pages: [1, 2]
    });
    renderProcessTable();
}

// ----------------------------------------------------
// OS Simulation Request Dispatcher
// ----------------------------------------------------
async function runOSSimulation() {
    try {
        writeConsole("Dispatching OS Simulation request...");
        const payload = {
            processes: activeProcesses.map(p => ({
                process_id: p.id,
                burst_time: p.burst,
                arrival_time: p.arrival,
                priority: p.priority,
                memory_pages: p.pages
            })),
            config: {
                algorithm: document.getElementById("os-algo").value,
                quantum: parseFloat(document.getElementById("os-quantum").value) || 2.0,
                context_switch_overhead: parseFloat(document.getElementById("os-overhead").value) || 0.1,
                ram_size_mb: parseInt(document.getElementById("os-ram").value) || 16,
                page_size_kb: 4,
                page_replacement_policy: document.getElementById("os-policy").value
            }
        };

        const res = await fetch(`${API_URL}/os/simulate`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
            credentials: "include"
        });
        
        if (!res.ok) throw new Error(await res.text());
        const data = await res.json();
        
        renderOSResults(data);
        writeConsole(`OS Simulation completed successfully.\nAvg Wait Time: ${data.average_waiting_time.toFixed(2)}ms\nAvg Turnaround: ${data.average_turnaround_time.toFixed(2)}ms`);
        
        runSystemDiagnostic({
            system_type: "OS",
            average_waiting_time: data.average_waiting_time,
            page_fault_rate: data.memory_summary.page_fault_rate,
            is_thrashing: data.memory_summary.is_thrashing
        });

    } catch (e) {
        writeConsole(`OS Simulation Failed: ${e.message}`, "error");
    }
}

function renderOSResults(data) {
    const container = document.getElementById("gantt-chart-div");
    container.innerHTML = "";
    
    if (!data.gantt_chart || data.gantt_chart.length === 0) {
        container.innerHTML = `<div class="gantt-empty">No gantt chart returned</div>`;
        return;
    }
    document.getElementById("gantt-legend-div").style.display = "flex";

    const totalDuration = data.gantt_chart[data.gantt_chart.length - 1].end_time;
    
    data.gantt_chart.forEach(item => {
        const block = document.createElement("div");
        block.className = "gantt-block";
        
        const duration = item.end_time - item.start_time;
        const widthPct = (duration / totalDuration) * 100;
        block.style.width = `calc(${widthPct}% - 2px)`;
        
        if (item.action === "context_switch") {
            block.style.background = "linear-gradient(135deg, var(--accent-pink), #B91C1C)";
            block.innerHTML = `<span>CS</span><span class="gantt-time">${duration.toFixed(1)}</span>`;
            block.style.color = "#FFF";
        } else if (item.action === "idle") {
            block.style.backgroundColor = "#334155";
            block.innerHTML = `<span>Idle</span><span class="gantt-time">${duration.toFixed(1)}</span>`;
            block.style.color = "#94A3B8";
        } else {
            const pidNum = parseInt(item.process_id.replace("P", "")) || 1;
            const hue = (pidNum * 137.5) % 360;
            block.style.backgroundColor = `hsl(${hue}, 85%, 65%)`;
            block.innerHTML = `<span>${item.process_id}</span><span class="gantt-time">${duration.toFixed(1)}</span>`;
            block.style.color = "#0B0F19";
        }
        container.appendChild(block);
    });

    document.getElementById("pg-faults-val").innerText = data.memory_summary.page_faults;
    document.getElementById("pg-rate-val").innerText = (data.memory_summary.page_fault_rate * 100).toFixed(1) + "%";

    const grid = document.getElementById("frames-grid-div");
    grid.innerHTML = "";

    const totalFrames = data.memory_summary.total_frames;
    const pageTable = data.memory_summary.page_table;

    const framesMap = new Array(totalFrames).fill(null);
    Object.keys(pageTable).forEach(pid => {
        pageTable[pid].forEach(entry => {
            if (entry.frame_num !== null) {
                framesMap[entry.frame_num] = { pid: pid, page: entry.page_num };
            }
        });
    });

    framesMap.forEach((frame, idx) => {
        const box = document.createElement("div");
        box.className = "frame-box";
        if (frame) {
            box.classList.add("allocated");
            box.innerHTML = `<span class="frame-num">Frame ${idx}</span><strong>${frame.pid}:Pg${frame.page}</strong>`;
        } else {
            box.innerHTML = `<span class="frame-num">Frame ${idx}</span><span style="color:var(--text-secondary);">Empty</span>`;
        }
        grid.appendChild(box);
    });

    targetMem = Math.min(100, Math.round(data.memory_summary.page_fault_rate * 100));
    targetCpu = Math.round(data.average_turnaround_time * 5);
    
    const badge = document.getElementById("thrashing-badge");
    if (data.memory_summary.is_thrashing) {
        badge.classList.remove("hidden");
    } else {
        badge.classList.add("hidden");
    }
}

// ----------------------------------------------------
// DBMS Simulation Request Dispatcher
// ----------------------------------------------------
async function runDBMSSimulation() {
    try {
        writeConsole("Dispatching DBMS query load testing...");
        const payload = {
            query_type: document.getElementById("dbms-qtype").value,
            num_records: parseInt(document.getElementById("dbms-rows").value) || 100000,
            range_fraction: (parseInt(document.getElementById("dbms-range-pct").value) || 10) / 100,
            config: {
                storage_type: document.getElementById("dbms-storage").value,
                block_size_bytes: parseInt(document.getElementById("dbms-block").value) || 4096,
                buffer_pool_size: parseInt(document.getElementById("dbms-buffer").value) || 100,
                pool_size: parseInt(document.getElementById("dbms-pool").value) || 10,
                index_type: document.getElementById("dbms-index").value
            },
            concurrent_requests: parseInt(document.getElementById("dbms-concurrent").value) || 1
        };

        const res = await fetch(`${API_URL}/dbms/query`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
            credentials: "include"
        });
        
        if (!res.ok) throw new Error(await res.text());
        const data = await res.json();
        
        renderDBMSResults(data, payload);
        writeConsole(`DBMS Simulator execution complete.\nEstimated latency: ${data.estimated_latency_ms.toFixed(2)}ms\nHops seek cost: ${data.node_hops}`);
        
        runSystemDiagnostic({
            system_type: "DBMS",
            latency_ms: data.estimated_latency_ms
        });

    } catch (e) {
        writeConsole(`DBMS Simulation Failed: ${e.message}`, "error");
    }
}

function renderDBMSResults(data, req) {
    document.getElementById("dbms-lat-val").innerText = data.estimated_latency_ms.toFixed(1) + "ms";
    document.getElementById("dbms-iops-val").innerText = Math.round(data.disk_iops);
    document.getElementById("dbms-hit-val").innerText = (data.cache_hit_ratio * 100).toFixed(0) + "%";
    document.getElementById("dbms-hops-val").innerText = data.node_hops;

    targetLat = Math.round(data.estimated_latency_ms);
    targetCpu = Math.round(data.cpu_utilization * 100);

    const btreeVisual = document.getElementById("btree-path-visual");
    btreeVisual.innerHTML = "";
    
    if (req.config.index_type === "B-Tree") {
        for (let i = 0; i < data.node_hops; i++) {
            if (i > 0) {
                const arrow = document.createElement("div");
                arrow.className = "tree-connector";
                arrow.innerText = "⬇";
                btreeVisual.appendChild(arrow);
            }
            const node = document.createElement("div");
            node.className = "tree-node";
            node.innerHTML = `<span>Node H${i}</span><strong>Block ${Math.round(Math.random() * 500)}</strong>`;
            btreeVisual.appendChild(node);
        }
    } else {
        btreeVisual.innerHTML = `<div class="table-empty" style="color:var(--accent-red)">Full scan scans all blocks sequentially. No B-Tree traversal path.</div>`;
    }

    const linearVisual = document.getElementById("linear-blocks-visual");
    linearVisual.innerHTML = "";
    
    const maxBlocksToRender = 16;
    const blocksRead = data.bytes_read / req.config.block_size_bytes;
    const totalBlocks = req.num_records * 128 / req.config.block_size_bytes;
    const readFraction = Math.min(1.0, blocksRead / totalBlocks);
    
    const highlightedCount = Math.ceil(readFraction * maxBlocksToRender);

    for (let i = 0; i < maxBlocksToRender; i++) {
        const block = document.createElement("div");
        block.className = "linear-block";
        if (i < highlightedCount) {
            block.classList.add("read");
            block.style.background = req.config.index_type === "B-Tree" ? "var(--accent-cyan)" : "var(--accent-amber)";
        }
        linearVisual.appendChild(block);
    }
}

// ----------------------------------------------------
// Concurrency Lock manager
// ----------------------------------------------------
function acquireLock() {
    const tx = document.getElementById("lock-tx").value.trim().toUpperCase();
    const res = document.getElementById("lock-res").value.trim().toUpperCase();
    const mode = document.getElementById("lock-mode").value;
    
    if (!tx || !res) return;
    
    writeConsole(`Transaction ${tx} requesting ${mode}-Lock on resource ${res}...`);
    
    const existingLockIndex = activeLocks.findIndex(l => l.resource === res);
    
    if (existingLockIndex === -1) {
        activeLocks.push({ resource: res, holders: [{ tx: tx, mode: mode }] });
        writeConsole(`Granted ${mode}-Lock on ${res} to ${tx}.`);
    } else {
        const lock = activeLocks[existingLockIndex];
        const hasExclusive = lock.holders.some(h => h.mode === "X");
        
        if (hasExclusive || mode === "X") {
            waitQueue.push({ tx: tx, resource: res, mode: mode });
            writeConsole(`Blocked: Resource ${res} held in conflicting mode. ${tx} queued in Wait-For table.`, "warning");
        } else {
            lock.holders.push({ tx: tx, mode: mode });
            writeConsole(`Granted Shared ${mode}-Lock on ${res} to reader ${tx}.`);
        }
    }
    
    renderLocks();
    detectDeadlocks();
}

function releaseLock() {
    const tx = document.getElementById("lock-tx").value.trim().toUpperCase();
    const res = document.getElementById("lock-res").value.trim().toUpperCase();
    
    if (!tx || !res) return;
    
    writeConsole(`Transaction ${tx} releasing locks on ${res}...`);
    
    const lockIndex = activeLocks.findIndex(l => l.resource === res);
    if (lockIndex !== -1) {
        const lock = activeLocks[lockIndex];
        lock.holders = lock.holders.filter(h => h.tx !== tx);
        
        if (lock.holders.length === 0) {
            activeLocks.splice(lockIndex, 1);
            
            const nextIndex = waitQueue.findIndex(w => w.resource === res);
            if (nextIndex !== -1) {
                const next = waitQueue.splice(nextIndex, 1)[0];
                activeLocks.push({ resource: next.resource, holders: [{ tx: next.tx, mode: next.mode }] });
                writeConsole(`Queued Transaction ${next.tx} granted ${next.mode}-Lock on resource ${next.resource}.`);
            }
        }
    }
    
    renderLocks();
    detectDeadlocks();
}

function clearLockManager() {
    activeLocks = [];
    waitQueue = [];
    renderLocks();
    detectDeadlocks();
    writeConsole("Cleared Lock Manager table states.");
}

function renderLocks() {
    const lockBody = document.querySelector("#lock-table tbody");
    lockBody.innerHTML = "";
    if (activeLocks.length === 0) {
        lockBody.innerHTML = `<tr><td colspan="3" class="table-empty">No locks held</td></tr>`;
    } else {
        activeLocks.forEach(l => {
            const tr = document.createElement("tr");
            const holders = l.holders.map(h => `${h.tx} (${h.mode})`).join(", ");
            const mode = l.holders.some(h => h.mode === "X") ? "Exclusive" : "Shared";
            tr.innerHTML = `<td><strong>${l.resource}</strong></td><td>${holders}</td><td>${mode}</td>`;
            lockBody.appendChild(tr);
        });
    }
    
    const waitBody = document.querySelector("#wait-table tbody");
    waitBody.innerHTML = "";
    if (waitQueue.length === 0) {
        waitBody.innerHTML = `<tr><td colspan="2" class="table-empty">No transactions waiting</td></tr>`;
    } else {
        waitQueue.forEach(w => {
            const tr = document.createElement("tr");
            tr.innerHTML = `<td><strong>${w.tx}</strong></td><td>Waiting for ${w.resource} (${w.mode})</td>`;
            waitBody.appendChild(tr);
        });
    }
}

function detectDeadlocks() {
    const adj = {};
    const transactions = new Set();
    
    waitQueue.forEach(w => {
        transactions.add(w.tx);
        const lock = activeLocks.find(l => l.resource === w.resource);
        if (lock) {
            lock.holders.forEach(h => {
                if (h.tx !== w.tx) {
                    if (!adj[w.tx]) adj[w.tx] = [];
                    adj[w.tx].push(h.tx);
                    transactions.add(h.tx);
                }
            });
        }
    });

    const visited = {};
    const path = [];
    const cycles = [];

    function dfs(node) {
        visited[node] = 0;
        path.push(node);
        
        const neighbors = adj[node] || [];
        for (let neighbor of neighbors) {
            if (visited[neighbor] === undefined) {
                dfs(neighbor);
            } else if (visited[neighbor] === 0) {
                const startIdx = path.indexOf(neighbor);
                cycles.push(path.slice(startIdx));
            }
        }
        
        path.pop();
        visited[node] = 1;
    }
    
    transactions.forEach(tx => {
        if (visited[tx] === undefined) dfs(tx);
    });

    const badge = document.getElementById("deadlock-badge");
    const graphDiv = document.getElementById("deadlock-graph-div");
    
    if (cycles.length > 0) {
        badge.classList.remove("hidden");
        writeConsole(`DEADLOCK ALERT: Cycle detected: ${cycles[0].join(" ➜ ")}`, "error");
        
        graphDiv.innerHTML = "";
        const cycle = cycles[0];
        const container = document.createElement("div");
        container.className = "cycle-diagram";
        
        cycle.forEach((node, i) => {
            if (i > 0) {
                const arrow = document.createElement("span");
                arrow.innerText = "➜";
                arrow.style.color = "var(--accent-pink)";
                container.appendChild(arrow);
            }
            const el = document.createElement("div");
            el.className = "cycle-node";
            el.innerText = node;
            container.appendChild(el);
        });
        const loopArrow = document.createElement("span");
        loopArrow.innerText = "➜ " + cycle[0];
        loopArrow.style.color = "var(--accent-pink)";
        loopArrow.style.fontStyle = "italic";
        container.appendChild(loopArrow);
        
        graphDiv.appendChild(container);
        
        targetLat = 1000;
        targetCpu = 5;
        
        runSystemDiagnostic({
            system_type: "DBMS",
            deadlocks: cycles
        });
    } else {
        badge.classList.add("hidden");
        graphDiv.innerHTML = `<div class="graph-empty">No deadlock dependencies active</div>`;
    }
}

// ----------------------------------------------------
// Faculty Preset Scenarios
// ----------------------------------------------------
function selectLabPreset() {
    const key = document.getElementById("lab-preset-select").value;
    activeLabKey = key;
    
    const panel = document.getElementById("lab-instructions-panel");
    const submitBtn = document.getElementById("lab-submit-btn");
    
    if (!key) {
        panel.classList.add("hidden");
        submitBtn.classList.add("hidden");
        return;
    }
    
    const preset = presets[key];
    document.getElementById("lab-title-text").innerText = preset.title;
    document.getElementById("lab-desc-text").innerText = preset.description;
    
    const list = document.getElementById("lab-assertions-list");
    list.innerHTML = "";
    preset.assertions.forEach(a => {
        const li = document.createElement("li");
        li.innerHTML = `<span>⚙️</span> ${a.desc}`;
        list.appendChild(li);
    });
    
    panel.classList.remove("hidden");
    submitBtn.classList.remove("hidden");
    
    if (key === "thrashing_lab" || key === "scheduling_overhead_lab") {
        document.getElementById("os-ram").value = preset.config.ram_size_mb || 16;
        if (preset.config.page_replacement_policy) {
            document.getElementById("os-policy").value = preset.config.page_replacement_policy;
        }
        if (preset.config.algorithm) {
            document.getElementById("os-algo").value = preset.config.algorithm;
        }
        if (preset.config.quantum) {
            document.getElementById("os-quantum").value = preset.config.quantum;
        }
        if (preset.config.context_switch_overhead) {
            document.getElementById("os-overhead").value = preset.config.context_switch_overhead;
        }
        
        activeProcesses = JSON.parse(JSON.stringify(preset.scenarios));
        renderProcessTable();
    }
    writeConsole(`Loaded Lab Preset: ${preset.title}. Awaiting execution submission...`);
}

async function submitLabPreset() {
    if (!activeLabKey) return;
    writeConsole("Submitting Lab configurations for validation grading...");
    
    try {
        const preset = presets[activeLabKey];
        let payload;
        
        if (preset) {
            payload = {
                module_id: activeLabKey,
                title: preset.title,
                system_type: activeLabKey === "deadlock_lab" ? "DBMS" : "OS",
                configuration: preset.config,
                scenarios: preset.scenarios,
                assertions: preset.assertions.map(a => ({
                    metric: a.metric,
                    operator: a.metric === "is_thrashing" ? "==" : ">=",
                    value: a.metric === "is_thrashing" ? true : (a.metric === "page_fault_rate" ? 0.6 : 1)
                }))
            };
        } else {
            payload = {
                module_id: activeLabKey,
                title: "Custom Lab",
                system_type: "OS",
                configuration: {},
                scenarios: [],
                assertions: []
            };
        }
        
        if (preset) {
            await fetch(`${API_URL}/schema/`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
                credentials: "include"
            });
        }
        
        const studentConfig = {};
        const activeTab = document.querySelector(".nav-btn.active").dataset.tab;
        
        if (activeTab === "os-tab" || activeLabKey === "thrashing_lab" || activeLabKey === "scheduling_overhead_lab") {
            studentConfig.ram_size_mb = parseInt(document.getElementById("os-ram").value);
            studentConfig.page_replacement_policy = document.getElementById("os-policy").value;
            studentConfig.quantum = parseFloat(document.getElementById("os-quantum").value);
            studentConfig.context_switch_overhead = parseFloat(document.getElementById("os-overhead").value);
        } else if (activeTab === "dbms-tab") {
            studentConfig.index_type = document.getElementById("dbms-index").value;
            studentConfig.storage_type = document.getElementById("dbms-storage").value;
            studentConfig.buffer_pool_size = parseInt(document.getElementById("dbms-buffer").value);
            studentConfig.pool_size = parseInt(document.getElementById("dbms-pool").value);
        } else {
            studentConfig.deadlocks = waitQueue.length > 0 ? 1 : 0;
        }
        
        const res = await fetch(`${API_URL}/schema/submit`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                module_id: activeLabKey,
                student_config: studentConfig
            }),
            credentials: "include"
        });
        
        const data = await res.json();
        renderLabResults(data);

    } catch (e) {
        writeConsole(`Lab submission failed: ${e.message}`, "error");
    }
}

function renderLabResults(data) {
    const resDiv = document.getElementById("lab-result-div");
    const banner = document.getElementById("lab-pass-fail-banner");
    const details = document.getElementById("lab-failed-details");
    
    details.innerHTML = "";
    resDiv.style.display = "block";
    
    if (data.passed) {
        resDiv.className = "lab-result-panel passed card";
        banner.innerText = "🏆 LAB GRADED: SUCCESSFUL PASS!";
        details.innerHTML = `<div class="grading-item" style="color:var(--accent-green)">All grading assertion checks matched parameters. Submission files ready.</div>`;
    } else {
        resDiv.className = "lab-result-panel failed card";
        banner.innerText = "❌ LAB GRADED: FAIL";
        data.failed_assertions.forEach(f => {
            const el = document.createElement("div");
            el.className = "grading-item";
            el.innerHTML = `Failed: Metric <strong>${f.metric}</strong> expected ${f.operator} ${f.expected}, but actual value was ${f.actual}`;
            details.appendChild(el);
        });
    }
}

// ----------------------------------------------------
// Real-Time Diagnostic Engine Client
// ----------------------------------------------------
async function runSystemDiagnostic(metrics) {
    try {
        const desc = getDiagnosticLogs(metrics);
        const consoleEl = document.getElementById("diagnostic-console");
        consoleEl.innerHTML = desc;
        consoleEl.scrollTop = consoleEl.scrollHeight;
    } catch (e) {}
}

function getDiagnosticLogs(metrics) {
    let diag = "";
    if (metrics.system_type === "OS") {
        if (metrics.is_thrashing) {
            diag += `<span style="color:var(--accent-pink)"><strong>[WARNING] Memory Thrashing Active</strong></span>\n`;
            diag += `Page Fault Rate: ${(metrics.page_fault_rate * 100).toFixed(1)}%\n`;
            diag += `Reason: Process reference stream exceeds frame capacity. CPU is context-switching pages instead of running instructions.\n`;
            diag += `Recommendation: Increase physical RAM size or optimize replacement algorithm to LRU.`;
        } else if (metrics.average_waiting_time > 15.0) {
            diag += `<span style="color:var(--accent-amber)"><strong>[WARN] High Scheduling Wait Times</strong></span>\n`;
            diag += `Average process ready time is high (${metrics.average_waiting_time.toFixed(1)}ms).\n`;
            diag += `Recommendation: Optimize Round Robin Quantum parameter or decrease context overhead.`;
        } else {
            diag += `<span style="color:var(--accent-green)"><strong>[OK] OS System Normal</strong></span>\n`;
            diag += `Execution complete within designed latency constraints.`;
        }
    } else {
        if (metrics.deadlocks && metrics.deadlocks.length > 0) {
            diag += `<span style="color:var(--accent-pink)"><strong>[CRITICAL] Deadlock Block Detected!</strong></span>\n`;
            diag += `Wait-For graph cycle paths detected: ${metrics.deadlocks[0].join(" ➜ ")}\n`;
            diag += `Reason: Multiple active threads hold exclusive locks on items requested by each other.\n`;
            diag += `Recommendation: Enforce strict acquisition indexes ordering or add transaction timeouts.`;
        } else if (metrics.latency_ms > 200.0) {
            diag += `<span style="color:var(--accent-amber)"><strong>[WARN] Storage I/O BottleNeck</strong></span>\n`;
            diag += `High latency ${metrics.latency_ms.toFixed(1)}ms. Hit Ratio is low.\n`;
            diag += `Recommendation: Enable B-Tree indexes or increase Buffer Page size.`;
        } else {
            diag += `<span style="color:var(--accent-green)"><strong>[OK] DBMS System Normal</strong></span>\n`;
            diag += `Transactions executing inside optimal buffer range pool bounds.`;
        }
    }
    return diag;
}

// ----------------------------------------------------
// WebSocket Telemetry Connection
// ----------------------------------------------------
function connectWebSocket() {
    writeConsole("Opening WebSocket telemetry stream...");
    wsClient = new WebSocket(WS_URL);
    
    wsClient.onopen = () => {
        document.getElementById("ws-dot").className = "status-dot connected";
        document.getElementById("ws-text").innerText = "Telemetry Online";
        document.getElementById("ws-toggle-btn").innerText = "Disconnect";
        writeConsole("WebSocket Connection established.");
    };
    
    wsClient.onmessage = (event) => {
        const state = JSON.parse(event.data);
        
        targetCpu = state.cpu_load;
        targetMem = state.memory_pressure;
        targetLat = state.latency_ms;
        
        const banner = document.getElementById("chaos-banner");
        const bannerText = document.getElementById("chaos-banner-text");
        
        if (state.chaos_active) {
            banner.style.display = "block";
            bannerText.innerText = `CHAOS ACTIVE: ${state.chaos_type.toUpperCase()}`;
            document.getElementById("thrashing-badge").classList.remove("hidden");
        } else {
            banner.style.display = "none";
            document.getElementById("thrashing-badge").classList.add("hidden");
        }
    };
    
    wsClient.onclose = () => {
        document.getElementById("ws-dot").className = "status-dot disconnected";
        document.getElementById("ws-text").innerText = "Telemetry Off";
        document.getElementById("ws-toggle-btn").innerText = "Connect";
        writeConsole("WebSocket stream disconnected.");
    };
    
    wsClient.onerror = (e) => {
        writeConsole("WebSocket Error occurred.", "error");
    };
}

function toggleWebSocket() {
    if (wsClient && wsClient.readyState === WebSocket.OPEN) {
        wsClient.close();
    } else {
        connectWebSocket();
    }
}

function triggerChaos(event) {
    if (wsClient && wsClient.readyState === WebSocket.OPEN) {
        writeConsole(`Sending Chaos command: ${event}...`);
        wsClient.send(JSON.stringify({ type: "chaos", event: event }));
    } else {
        writeConsole("Cannot trigger chaos. Telemetry connection offline.", "warning");
    }
}

function resetChaos() {
    if (wsClient && wsClient.readyState === WebSocket.OPEN) {
        writeConsole("Sending Reset Chaos command...");
        wsClient.send(JSON.stringify({ type: "reset" }));
    }
}

// ----------------------------------------------------
// Telemetry Canvas Dial Rendering
// ----------------------------------------------------
function initTelemetryDials() {
    function animate() {
        curCpu += (targetCpu - curCpu) * 0.1;
        curMem += (targetMem - curMem) * 0.1;
        curLat += (targetLat - curLat) * 0.1;
        
        drawDial("cpu-dial", curCpu, 100, "var(--accent-cyan)", "%");
        drawDial("mem-dial", curMem, 100, "var(--accent-green)", "%");
        drawDial("lat-dial", Math.min(1000, curLat), 1000, "var(--accent-amber)", "ms");
        
        requestAnimationFrame(animate);
    }
    requestAnimationFrame(animate);
}

function drawDial(canvasId, val, maxVal, color, unit) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    
    const x = canvas.width / 2;
    const y = canvas.height / 2;
    const radius = 48;
    
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, 2 * Math.PI);
    ctx.strokeStyle = "rgba(255, 255, 255, 0.03)";
    ctx.lineWidth = 8;
    ctx.stroke();
    
    ctx.beginPath();
    const pct = val / maxVal;
    const endAngle = -0.5 * Math.PI + pct * 2 * Math.PI;
    ctx.arc(x, y, radius, -0.5 * Math.PI, endAngle);
    ctx.strokeStyle = color;
    ctx.lineWidth = 6;
    ctx.lineCap = "round";
    
    ctx.shadowColor = color;
    ctx.shadowBlur = 10;
    ctx.stroke();
    
    ctx.shadowBlur = 0;
    
    const valText = val.toFixed(0);
    const overlayId = canvasId.replace("-dial", "-val");
    const overlay = document.getElementById(overlayId);
    if (overlay) {
        overlay.innerText = valText + unit;
        overlay.style.color = color;
    }
}

// ----------------------------------------------------
// UI Console logs
// ----------------------------------------------------
function writeConsole(text, type = "info") {
    const consoleEl = document.getElementById("diagnostic-console");
    let color = "#10B981";
    if (type === "warning") color = "var(--accent-amber)";
    if (type === "error") color = "var(--accent-pink)";
    
    const timestamp = new Date().toLocaleTimeString();
    const formatted = `[${timestamp}] <span style="color:${color}">${text}</span><br/>`;
    
    consoleEl.innerHTML += formatted;
    consoleEl.scrollTop = consoleEl.scrollHeight;
}
