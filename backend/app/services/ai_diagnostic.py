import httpx
from app.core.config import settings

class AIDiagnosticService:
    @staticmethod
    def get_diagnostic(logs_and_metrics: dict) -> str:
        if settings.GEMINI_API_KEY:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={settings.GEMINI_API_KEY}"
                prompt = f"""
                You are a senior systems performance engineer. Analyze the following simulation metrics and diagnose any bottleneck or failure:
                {logs_and_metrics}
                
                Provide:
                1. Root-cause explanation.
                2. Recommendations to fix it.
                Keep it concise and clear.
                """
                response = httpx.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=10.0)
                if response.status_code == 200:
                    return response.json()["candidates"][0]["content"]["parts"][0]["text"]
            except Exception as e:
                pass
        system_type = logs_and_metrics.get("system_type", "OS").upper()
        if system_type == "OS":
            is_thrashing = logs_and_metrics.get("is_thrashing", False)
            avg_waiting = logs_and_metrics.get("average_waiting_time", 0.0)
            fault_rate = logs_and_metrics.get("page_fault_rate", 0.0)
            diag = "### Systems Analysis Diagnostic (Deterministic Mode)\n\n"
            if is_thrashing:
                diag += "**Root Cause**: **Memory Thrashing Detected.**\n"
                diag += f"- The page fault rate is {fault_rate:.2%}.\n"
                diag += "- The processes are requesting pages at a rate higher than the frame allocation limit. The system is spending all its time swapping pages in/out of storage instead of executing instructions.\n"
                diag += "**Recommendations**:\n"
                diag += "1. Increase the physical RAM size allocation.\n"
                diag += "2. Reduce the page replacement overhead or choose a more efficient replacement policy (e.g., LRU over FIFO).\n"
                diag += "3. Decrease the number of active concurrent processes (reduce multi-programming level).\n"
            elif avg_waiting > 10.0:
                diag += "**Root Cause**: **High Scheduling Latency.**\n"
                diag += f"- Average process waiting time is high ({avg_waiting:.2f} ms).\n"
                diag += "- Processes are spending too much time in the READY queue.\n"
                diag += "**Recommendations**:\n"
                diag += "1. Optimize the scheduling quantum (if using Round Robin). A quantum that is too low increases context-switch overhead; too high increases response time.\n"
                diag += "2. Change context-switch overhead delay configuration.\n"
            else:
                diag += "**Status**: **System is Healthy.**\n"
                diag += "- Process wait times and page fault ratios are within healthy design parameters.\n"
            return diag
        else:
            latency = logs_and_metrics.get("latency_ms", 0.0)
            cache_hit = logs_and_metrics.get("cache_hit_ratio", 1.0)
            deadlocks = logs_and_metrics.get("deadlocks", [])
            wait_time = logs_and_metrics.get("concurrency_wait_ms", 0.0)
            diag = "### Database Performance Diagnostic (Deterministic Mode)\n\n"
            if deadlocks:
                diag += "**Root Cause**: **Deadlock Cycle Detected.**\n"
                diag += f"- Cycle details: {deadlocks}\n"
                diag += "- Multiple concurrent transactions have acquired locks on different resources and are waiting for each other, creating a circular dependency.\n"
                diag += "**Recommendations**:\n"
                diag += "1. Enforce a strict ordering of resource acquisitions across all transactions.\n"
                diag += "2. Use shorter transactions to release locks faster.\n"
                diag += "3. Implement a retry mechanism with random backoff when a deadlock is detected.\n"
            elif wait_time > 10.0:
                diag += "**Root Cause**: **Connection Pool Exhaustion.**\n"
                diag += f"- Transactions are waiting an average of {wait_time:.2f} ms in the queue to get a connection pool slot.\n"
                diag += "- Concurrency load exceeds pool allocation capacity.\n"
                diag += "**Recommendations**:\n"
                diag += "1. Increase the Connection Pool size.\n"
                diag += "2. Optimize query speeds so connections are returned to the pool faster.\n"
            elif cache_hit < 0.3:
                diag += "**Root Cause**: **I/O Bottleneck / Cache Miss Saturation.**\n"
                diag += f"- Buffer pool cache hit ratio is extremely low ({cache_hit:.2%}).\n"
                diag += "- A high percentage of queries require disk page fetches, causing severe random I/O latency.\n"
                diag += "**Recommendations**:\n"
                diag += "1. Increase buffer pool page capacity.\n"
                diag += "2. Build covering B-Tree indexes to avoid scanning the entire database blocks.\n"
            else:
                diag += "**Status**: **DBMS is Healthy.**\n"
                diag += "- Latency curves, lock queues, and buffer caches are operating optimally.\n"
            return diag
