class DBMSSimulationCostModel:
    def __init__(self, disk_seek_ms: float = 8.0, disk_transfer_mbps: float = 100.0, cpu_latency_ms: float = 0.05):
        self.disk_seek_ms = disk_seek_ms
        self.disk_transfer_mbps = disk_transfer_mbps
        self.cpu_latency_ms = cpu_latency_ms

    def calculate_cost(
        self, hops: int, bytes_read: int, is_sequential: bool = False, cache_hit_ratio: float = 0.0, concurrent_requests: int = 1, pool_size: int = 10
    ) -> dict:
        disk_hops = hops * (1.0 - cache_hit_ratio)
        disk_bytes_read = bytes_read * (1.0 - cache_hit_ratio)
        if is_sequential:
            seek_cost = self.disk_seek_ms if disk_hops > 0 else 0.0
        else:
            seek_cost = disk_hops * self.disk_seek_ms
        transfer_speed_bytes_ms = (self.disk_transfer_mbps * 1024 * 1024) / 1000.0
        transfer_cost = disk_bytes_read / transfer_speed_bytes_ms if transfer_speed_bytes_ms > 0 else 0.0
        disk_latency = seek_cost + transfer_cost
        cpu_latency = hops * self.cpu_latency_ms
        base_latency = disk_latency + cpu_latency
        concurrency_wait_ms = 0.0
        if concurrent_requests > pool_size:
            queue_depth = concurrent_requests - pool_size
            concurrency_wait_ms = (base_latency * queue_depth) / pool_size
        total_latency = base_latency + concurrency_wait_ms
        estimated_iops = disk_hops / (total_latency / 1000.0) if total_latency > 0 else 0.0
        cpu_utilization = min(100.0, (cpu_latency / total_latency) * 100.0) if total_latency > 0 else 0.0
        return {
            "estimated_latency_ms": total_latency,
            "disk_iops": estimated_iops,
            "cpu_utilization": cpu_utilization,
            "concurrency_pool_wait_ms": concurrency_wait_ms,
            "disk_latency_ms": disk_latency,
            "cpu_latency_ms": cpu_latency
        }
