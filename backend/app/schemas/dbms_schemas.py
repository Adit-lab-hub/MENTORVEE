from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class DBMSConfig(BaseModel):
    storage_type: str = "SSD"  # SSD, HDD
    block_size_bytes: int = 4096
    buffer_pool_size: int = 100
    pool_size: int = 10
    index_type: str = "B-Tree" # B-Tree, Linear Scan

class DBMSQueryRequest(BaseModel):
    query_type: str = "point"  # point, range, scan
    num_records: int = 100000
    range_fraction: float = 0.1
    config: DBMSConfig
    concurrent_requests: int = 1

class LockRequest(BaseModel):
    tx_id: str
    resource_id: str
    lock_type: str

class LockRelease(BaseModel):
    tx_id: str
    resource_id: str

class ConcurrencySessionState(BaseModel):
    locks_held: Dict[str, List[str]]
    wait_queue: Dict[str, str]
    deadlocks_detected: List[List[str]]

class DBMSSimulationResult(BaseModel):
    estimated_latency_ms: float
    disk_iops: float
    cache_hit_ratio: float
    cpu_utilization: float
    btree_height: int
    node_hops: int
    bytes_read: int
    concurrency_pool_wait_ms: float
    warnings: List[str]
