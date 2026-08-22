# SysSandbox - User & Interactive Operations Manual

Welcome to **SysSandbox (Concept-to-System)**. This sandbox is an interactive educational engineering platform designed to bridge theoretical computer science concepts (operating systems scheduling, virtual memory paging, database access paths, and locking concurrency) with real-world system telemetry and failure engineering.

---

## 1. Getting Started & Installation

To run this sandbox locally on any machine:
1. Clone the repository and navigate into it:
   ```bash
   git clone https://github.com/Adit-lab-hub/SIH_Hackathon.git
   cd SIH_Hackathon
   ```
2. Create and activate a Python virtual environment:
   - **Windows**: `python -m venv .venv` then `.venv\Scripts\activate`
   - **Mac/Linux**: `python -m venv .venv` then `source .venv/bin/activate`
3. Install the dependencies:
   ```bash
   pip install -r backend/requirements.txt
   ```
4. Run the Uvicorn FastAPI backend:
   - **Windows**: `$env:PYTHONPATH="backend"; python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`
   - **Mac/Linux**: `export PYTHONPATH="backend"; python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`
5. Run the Frontend static server:
   ```bash
   python -m http.server 3000 --directory frontend
   ```
6. Open your browser and navigate to **`http://localhost:3000`**.

---

## 2. Core Simulation Modules Guide

### 💻 Module 1: OS Simulator (CPU Scheduling & Memory Paging)
This module simulates how operating systems manage executing processes on a single CPU core and schedule pages in physical RAM frames.

#### Interactive Configurations:
- **Scheduling Algorithms**: 
  - *FCFS*: Non-preemptive scheduling based on arrival times.
  - *Round Robin (RR)*: Preemptive scheduling where each process is executed for a maximum of a designated time quantum.
  - *Priority*: Scheduled by the process priority integer (higher priority value executes first).
  - *MLFQ (Multi-level Feedback Queue)*: Demotes processes to lower priority queues (Q0 -> Q1 -> Q2) if they exceed their time quantum, preventing starvation with promotion aging.
- **Context Switch Cost**: Configures the time penalty (in milliseconds) incurred when the CPU switches execution context from one process to another.
- **RAM Size & Page Replacement Policy**: Configures total memory page frames. Choose **LRU** (Least Recently Used) or **FIFO** (First-In, First-Out) frame swapping.

#### 💡 Core Failure Scenario: Memory Thrashing
* **What is it?** When active processes request virtual pages that exceed the physical frame capacity of RAM, the system spends all its cycles swapping pages in and out of swap space rather than executing process burst times.
* **How to trigger it:**
  1. Add a process with a large page stream (e.g. `1,2,3,4,5,6,7,8,9,10`).
  2. In the configurations, lower the **RAM Size** to `4MB` or `8MB` (which reduces physical frame capacity).
  3. Click **Simulate System Execution**.
  4. **Observe**: The **page fault rate** will spike, a flashing `"THRASHING ACTIVE"` badge will appear, and the Access Latency dial will spike exponentially.

---

### 🗄️ Module 2: DBMS Simulator (Index Paths & Storage Latency)
This module computes disk I/O and query latency curves based on node hops, block sizes, and connection pool queuing.

#### Interactive Configurations:
- **Index Type**: Choose **B-Tree** index node hops traversal vs. **Linear Scan** full block search.
- **Storage Class**: SSD (fast random access read, seek ~0.1ms) vs. HDD (slower seek penalty ~8.0ms).
- **Buffer Pool & Conn Pool**: Limits cache hit ratios and concurrent connection thread slots.
- **Query Profile**: Configure POINT (single row) vs. RANGE queries.

#### 💡 Core System Concept: Search Complexity Hops
* **What is it?** A point query on a B-Tree scales logarithmically ($O(\log_b N)$) based on key size branching factor, requiring only $h$ block hops. A Linear Scan scales linearly ($O(N)$), reading on average $N / 2$ data blocks.
* **How to compare them:**
  1. Toggle **Index Type** to `B-Tree` and click **Execute Load**. Observe the low node hops and estimated latency.
  2. Toggle to `Linear Scan` and re-run. Observe the massive jump in blocks read (colored amber in the block grid) and the corresponding latency penalty.

---

### 🔒 Module 3: Lock Manager (Deadlocks & Wait-For Graphs)
This module simulates row-level concurrency control where transactions compete for Shared (Read) or Exclusive (Write) locks.

#### Interactive Configurations:
- **Transaction ID & Resource ID**: Configure transaction and lock requests.
- **Lock Mode**: **Shared (S)** allows multiple concurrent readers; **Exclusive (X)** grants lock to a single transaction, blocking other readers or writers.

#### 💡 Core Concurrency Concept: Transaction Deadlocks
* **What is it?** A deadlock occurs when two or more transactions hold locks on different resources and are waiting on each other in a circular dependency.
* **How to trigger it:**
  1. Type **T1**, **R1**, select **Exclusive**, click **Request Lock** (T1 holds X-lock on R1).
  2. Type **T2**, **R2**, select **Exclusive**, click **Request Lock** (T2 holds X-lock on R2).
  3. Type **T1**, **R2**, select **Exclusive**, click **Request Lock** (T1 blocks waiting for R2).
  4. Type **T2**, **R1**, select **Exclusive**, click **Request Lock** (T2 blocks waiting for R1).
  5. **Observe**: A flashing `"DEADLOCK DETECTED!"` warning will appear, and the **Wait-For Graph** cycle diagram will visualize the circle `T1 ➜ T2 ➜ T1`.

---

## 3. Real-Time Telemetry & Chaos Control Center

Located at the top right of the dashboard, this panel shows real-time metrics streaming over active WebSockets from the backend server.

- **CPU Saturation Dial**: Measures scheduling algorithm work.
- **Memory Page Pressure Dial**: Displays page fault ratios.
- **Access Latency Dial**: Shows query wait times and database seek delays.
- **Chaos Injection Console**:
  - **Latency Spike**: Simulates disk degradation (latency increases).
  - **Thrashing**: Floods memory with page faults (latency spikes, CPU drops).
  - **Pool Deplete**: Satures connection pool (high queuing delay).
- **Diagnostic Root-Cause Engine**: Outputs systems diagnostic explanations in the console detailing bottlenecks and recommended architectural fixes.
