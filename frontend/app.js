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

// Initialize
document.addEventListener("DOMContentLoaded", () => {
    initTabs();
    initProcessTable();
    initTelemetryDials();
    connectWebSocket();
    
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
});

// Sidebar tabs toggles
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
            
            // Map configuration tab to simulation output panel
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
            }
        });
    });
}

// OS Process Configuration Table Editor
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
            body: JSON.stringify(payload)
        });
        
        if (!res.ok) throw new Error(await res.text());
        const data = await res.json();
        
        renderOSResults(data);
        writeConsole(`OS Simulation completed successfully.\nAvg Wait Time: ${data.average_waiting_time.toFixed(2)}ms\nAvg Turnaround: ${data.average_turnaround_time.toFixed(2)}ms`);
        
        // Feed into Diagnostics console
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
    // 1. Render Gantt Chart Timeline
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
            // Standard executing blocks (dynamic process colors)
            const pidNum = parseInt(item.process_id.replace("P", "")) || 1;
            const hue = (pidNum * 137.5) % 360; // Deterministic distribution
            block.style.backgroundColor = `hsl(${hue}, 85%, 65%)`;
            block.innerHTML = `<span>${item.process_id}</span><span class="gantt-time">${duration.toFixed(1)}</span>`;
            block.style.color = "#0B0F19";
        }
        container.appendChild(block);
    });

    // 2. Render Paging frames
    document.getElementById("pg-faults-val").innerText = data.memory_summary.page_faults;
    document.getElementById("pg-rate-val").innerText = (data.memory_summary.page_fault_rate * 100).toFixed(1) + "%";

    const grid = document.getElementById("frames-grid-div");
    grid.innerHTML = "";

    // Render active allocated frames
    const totalFrames = data.memory_summary.total_frames;
    const pageTable = data.memory_summary.page_table;

    // Build frame to page map
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

    // Update Telemetry Memory level targets
    targetMem = Math.min(100, Math.round(data.memory_summary.page_fault_rate * 100));
    targetCpu = Math.round(data.average_turnaround_time * 5); // Simulated scaling
    
    // Thrashing badge
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
            body: JSON.stringify(payload)
        });
        
        if (!res.ok) throw new Error(await res.text());
        const data = await res.json();
        
        renderDBMSResults(data, payload);
        writeConsole(`DBMS Query simulation completed successfully.\nAvg Latency: ${data.estimated_latency_ms.toFixed(2)}ms\nIOPS: ${data.disk_iops.toFixed(1)}`);
        
        // Feed into Diagnostics console
        runSystemDiagnostic({
            system_type: "DBMS",
            latency_ms: data.estimated_latency_ms,
            cache_hit_ratio: data.cache_hit_ratio,
            concurrency_wait_ms: data.concurrency_pool_wait_ms,
            deadlocks: []
        });

    } catch (e) {
        writeConsole(`DBMS Simulation Failed: ${e.message}`, "error");
    }
}

function renderDBMSResults(data, payload) {
    document.getElementById("dbms-lat-val").innerText = data.estimated_latency_ms.toFixed(2) + "ms";
    document.getElementById("dbms-iops-val").innerText = Math.round(data.disk_iops);
    document.getElementById("dbms-hit-val").innerText = (data.cache_hit_ratio * 100).toFixed(0) + "%";
    document.getElementById("dbms-hops-val").innerText = data.node_hops;

    // Update Live Dials Targets
    targetLat = Math.round(data.estimated_latency_ms);
    targetCpu = Math.round(data.cpu_utilization);

    // 1. Render Index Traversal Paths comparison
    const pathVis = document.getElementById("btree-path-visual");
    pathVis.innerHTML = "";
    if (payload.config.index_type === "B-Tree") {
        for (let i = 0; i < data.node_hops; i++) {
            if (i > 0) {
                const arrow = document.createElement("div");
                arrow.className = "tree-arrow";
                arrow.innerText = "⬇";
                pathVis.appendChild(arrow);
            }
            const node = document.createElement("div");
            node.className = "tree-node-visual";
            node.innerHTML = `<span>Page Node Lvl ${i}</span>`;
            pathVis.appendChild(node);
        }
    } else {
        pathVis.innerHTML = `<div style="font-size:0.8rem; color:var(--accent-amber);">B-Tree disabled (Sequential Table Scan active)</div>`;
    }

    // 2. Render linear read blocks representation
    const blockVis = document.getElementById("linear-blocks-visual");
    blockVis.innerHTML = "";
    
    // Scale down number of blocks to display (e.g. max 40 blocks representation)
    const blocksCount = Math.min(60, data.node_hops);
    for (let i = 0; i < 40; i++) {
        const block = document.createElement("div");
        block.className = "block-box";
        if (i < blocksCount) {
            block.classList.add("read");
        }
        blockVis.appendChild(block);
    }
}

// ----------------------------------------------------
// Concurrency lock manager controller
// ----------------------------------------------------
async function acquireLock() {
    const txId = document.getElementById("lock-tx").value.trim().toUpperCase();
    const resId = document.getElementById("lock-res").value.trim().toUpperCase();
    const mode = document.getElementById("lock-mode").value;
    
    if (!txId || !resId) return;
    
    writeConsole(`Requesting Lock: Tx=${txId}, Res=${resId}, Mode=${mode}...`);
    
    // We will model the local acquisition logic to display in GUI
    // This executes client side state mirroring the locking engines behaviour.
    const isConflict = checkLockConflict(txId, resId, mode);
    
    if (!isConflict) {
        // Lock acquired!
        activeLocks.push({ tx_id: txId, resource_id: resId, lock_type: mode });
        // Remove from wait queue if was in it
        waitQueue = waitQueue.filter(w => w.tx_id !== txId);
        writeConsole(`Lock Acquired successfully: Transaction ${txId} holds ${mode} on ${resId}.`);
    } else {
        // Blocked!
        waitQueue.push({ tx_id: txId, resource_id: resId });
        writeConsole(`Lock BLOCKED: Transaction ${txId} waiting for resource ${resId} to release.`, "warning");
    }
    
    renderLockTables();
    checkDeadlockCycles();
}

function checkLockConflict(txId, resId, mode) {
    // Shared compatible with other Shared, Exclusive is incompatible with anything
    for (let holder of activeLocks) {
        if (holder.resource_id === resId && holder.tx_id !== txId) {
            if (mode === "X" || holder.lock_type === "X") {
                return true;
            }
        }
    }
    return false;
}

function releaseLock() {
    const txId = document.getElementById("lock-tx").value.trim().toUpperCase();
    const resId = document.getElementById("lock-res").value.trim().toUpperCase();
    
    if (!txId || !resId) return;
    
    writeConsole(`Releasing Lock: Tx=${txId}, Res=${resId}...`);
    activeLocks = activeLocks.filter(l => !(l.tx_id === txId && l.resource_id === resId));
    
    writeConsole(`Released Lock successfully.`);
    
    // Evaluate if blocked waiters can now acquire
    reevaluateWaiters();
    renderLockTables();
    checkDeadlockCycles();
}

function reevaluateWaiters() {
    let recheck = true;
    while (recheck) {
        recheck = false;
        for (let i = 0; i < waitQueue.length; i++) {
            const waiter = waitQueue[i];
            const hasConflict = checkLockConflict(waiter.tx_id, waiter.resource_id, "X"); // Defaulting check
            if (!hasConflict) {
                // Acquire!
                activeLocks.push({ tx_id: waiter.tx_id, resource_id: waiter.resource_id, lock_type: "X" });
                waitQueue.splice(i, 1);
                writeConsole(`Waiter Woke Up: Transaction ${waiter.tx_id} acquired lock on ${waiter.resource_id}.`);
                recheck = true;
                break;
            }
        }
    }
}

function clearLockManager() {
    activeLocks = [];
    waitQueue = [];
    renderLockTables();
    checkDeadlockCycles();
    writeConsole("Lock manager cleaned. All locks released.");
}

function renderLockTables() {
    const lBody = document.querySelector("#lock-table tbody");
    lBody.innerHTML = "";
    if (activeLocks.length === 0) {
        lBody.innerHTML = `<tr><td colspan="3" class="table-empty">No locks held</td></tr>`;
    } else {
        activeLocks.forEach(l => {
            const tr = document.createElement("tr");
            tr.innerHTML = `<td>${l.resource_id}</td><td>${l.tx_id}</td><td><strong>${l.lock_type}</strong></td>`;
            lBody.appendChild(tr);
        });
    }

    const wBody = document.querySelector("#wait-table tbody");
    wBody.innerHTML = "";
    if (waitQueue.length === 0) {
        wBody.innerHTML = `<tr><td colspan="2" class="table-empty">No transactions waiting</td></tr>`;
    } else {
        waitQueue.forEach(w => {
            const tr = document.createElement("tr");
            tr.innerHTML = `<td>${w.tx_id}</td><td>${w.resource_id}</td>`;
            wBody.appendChild(tr);
        });
    }
}

function checkDeadlockCycles() {
    // DFS Cycle detection on Wait-for-graph
    // waitQueue maps: Tx -> Res, activeLocks maps: Res -> Tx (holder)
    // Graph builds: Tx_a -> Tx_b if Tx_a is waiting for Res locked by Tx_b
    const adj = {};
    const transactions = new Set();
    
    waitQueue.forEach(w => {
        transactions.add(w.tx_id);
        const holders = activeLocks.filter(l => l.resource_id === w.resource_id).map(l => l.tx_id);
        if (!adj[w.tx_id]) adj[w.tx_id] = new Set();
        holders.forEach(h => {
            adj[w.tx_id].add(h);
            transactions.add(h);
        });
    });
    
    const cycles = [];
    const visited = {}; // 0=visiting, 1=visited
    let path = [];
    
    function dfs(node) {
        visited[node] = 0;
        path.push(node);
        
        const neighbors = adj[node] || [];
        for (let neighbor of neighbors) {
            if (visited[neighbor] === undefined) {
                dfs(neighbor);
            } else if (visited[neighbor] === 0) {
                // Cycle!
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
        
        // Render simple cycle nodes
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
        // Loop arrow
        const loopArrow = document.createElement("span");
        loopArrow.innerText = "➜ " + cycle[0];
        loopArrow.style.color = "var(--accent-pink)";
        loopArrow.style.fontStyle = "italic";
        container.appendChild(loopArrow);
        
        graphDiv.appendChild(container);
        
        // Push telemetry changes
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

let activeLabKey = "";

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
    
    // Auto load configuration templates to editors
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
        // Create full payload payload
        const payload = {
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
        
        // 1. POST schema registration
        await fetch(`${API_URL}/schema/`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        
        // 2. Submit student overrides configurations
        const studentConfig = {};
        if (activeLabKey === "thrashing_lab" || activeLabKey === "scheduling_overhead_lab") {
            studentConfig.ram_size_mb = parseInt(document.getElementById("os-ram").value);
            studentConfig.page_replacement_policy = document.getElementById("os-policy").value;
            studentConfig.quantum = parseFloat(document.getElementById("os-quantum").value);
            studentConfig.context_switch_overhead = parseFloat(document.getElementById("os-overhead").value);
        } else {
            // Lock manager check
            studentConfig.deadlocks = waitQueue.length > 0 ? 1 : 0;
        }
        
        const res = await fetch(`${API_URL}/schema/submit`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                module_id: activeLabKey,
                student_config: studentConfig
            })
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
        const res = await fetch(`${API_URL}/ws/telemetry`); // Just dummy request or direct simulation metrics analyze
        // Call local Expert Rules via fallback diagnostic client logic
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
    } else { // DBMS
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
        
        // Target telemetry values update
        targetCpu = state.cpu_load;
        targetMem = state.memory_pressure;
        targetLat = state.latency_ms;
        
        // Show/hide Chaos banner
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
    // Canvas animation loop
    function animate() {
        // Interpolate current values to target values
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
    
    // 1. Draw track ring
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, 2 * Math.PI);
    ctx.strokeStyle = "rgba(255, 255, 255, 0.03)";
    ctx.lineWidth = 8;
    ctx.stroke();
    
    // 2. Draw glow ring
    ctx.beginPath();
    const pct = val / maxVal;
    const endAngle = -0.5 * Math.PI + pct * 2 * Math.PI;
    ctx.arc(x, y, radius, -0.5 * Math.PI, endAngle);
    ctx.strokeStyle = color;
    ctx.lineWidth = 6;
    ctx.lineCap = "round";
    
    // Shadow glow
    ctx.shadowColor = color;
    ctx.shadowBlur = 10;
    ctx.stroke();
    
    // Reset shadow
    ctx.shadowBlur = 0;
    
    // Update numerical value text in HTML overlay
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
    let color = "#10B981"; // green
    if (type === "warning") color = "var(--accent-amber)";
    if (type === "error") color = "var(--accent-pink)";
    
    const timestamp = new Date().toLocaleTimeString();
    const formatted = `[${timestamp}] <span style="color:${color}">${text}</span><br/>`;
    
    // Append but keep max rows
    consoleEl.innerHTML += formatted;
    consoleEl.scrollTop = consoleEl.scrollHeight;
}
