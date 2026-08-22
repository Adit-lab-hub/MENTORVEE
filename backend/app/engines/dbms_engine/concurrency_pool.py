from typing import Dict, List, Set, Tuple

class DBMSLockManager:
    def __init__(self):
        self.lock_table: Dict[str, List[Tuple[str, str]]] = {}
        self.wait_queue: Dict[str, str] = {}

    def reset(self):
        self.lock_table.clear()
        self.wait_queue.clear()

    def acquire_lock(self, tx_id: str, resource_id: str, lock_type: str) -> bool:
        lock_type = lock_type.upper()
        if resource_id not in self.lock_table:
            self.lock_table[resource_id] = [(tx_id, lock_type)]
            if tx_id in self.wait_queue:
                del self.wait_queue[tx_id]
            return True
        existing_locks = self.lock_table[resource_id]
        can_acquire = True
        for holder_id, holder_type in existing_locks:
            if holder_id == tx_id:
                continue
            if lock_type == "X" or holder_type == "X":
                can_acquire = False
                break
        if can_acquire:
            if not any(holder_id == tx_id and holder_type == lock_type for holder_id, holder_type in existing_locks):
                existing_locks.append((tx_id, lock_type))
            if tx_id in self.wait_queue:
                del self.wait_queue[tx_id]
            return True
        else:
            self.wait_queue[tx_id] = resource_id
            return False

    def release_lock(self, tx_id: str, resource_id: str):
        if resource_id in self.lock_table:
            self.lock_table[resource_id] = [
                (tid, ltype) for tid, ltype in self.lock_table[resource_id] if tid != tx_id
            ]
            if not self.lock_table[resource_id]:
                del self.lock_table[resource_id]
        waiters_to_remove = [tid for tid, res_id in self.wait_queue.items() if res_id == resource_id]
        for tid in waiters_to_remove:
            if tid in self.wait_queue:
                del self.wait_queue[tid]

    def detect_deadlocks(self) -> List[List[str]]:
        graph: Dict[str, Set[str]] = {}
        for tx_id, resource_id in self.wait_queue.items():
            if resource_id in self.lock_table:
                holders = [holder_id for holder_id, _ in self.lock_table[resource_id]]
                graph[tx_id] = set(holders)
        cycles = []
        visited = {}
        path = []
        def dfs(node: str):
            visited[node] = 0
            path.append(node)
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor)
                elif visited[neighbor] == 0:
                    cycle_start = path.index(neighbor)
                    cycles.append(path[cycle_start:].copy())
            path.pop()
            visited[node] = 1
        for node in graph:
            if node not in visited:
                dfs(node)
        return cycles
