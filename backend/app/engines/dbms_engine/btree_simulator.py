import math

class BTreeSimulator:
    def __init__(self, block_size_bytes: int = 4096, key_size_bytes: int = 16, pointer_size_bytes: int = 8, record_size_bytes: int = 128):
        self.block_size_bytes = block_size_bytes
        self.key_size_bytes = key_size_bytes
        self.pointer_size_bytes = pointer_size_bytes
        self.record_size_bytes = record_size_bytes

    def calculate_metrics(self, num_records: int, range_fraction: float = 0.1) -> dict:
        node_capacity = math.floor((self.block_size_bytes + self.key_size_bytes) / (self.pointer_size_bytes + self.key_size_bytes))
        if node_capacity < 3:
            node_capacity = 3
        if num_records > 0:
            btree_height = max(1, math.ceil(math.log(num_records, node_capacity)))
        else:
            btree_height = 0
        btree_point_hops = btree_height
        btree_point_bytes = btree_point_hops * self.block_size_bytes
        records_per_block = math.floor(self.block_size_bytes / self.record_size_bytes)
        if records_per_block < 1:
            records_per_block = 1
        total_data_blocks = math.ceil(num_records / records_per_block)
        linear_scan_point_hops = math.ceil(total_data_blocks / 2)
        linear_scan_point_bytes = linear_scan_point_hops * self.block_size_bytes
        num_range_records = math.ceil(num_records * range_fraction)
        range_blocks = math.ceil(num_range_records / records_per_block)
        btree_range_hops = btree_height + range_blocks
        btree_range_bytes = btree_range_hops * self.block_size_bytes
        linear_scan_range_hops = total_data_blocks
        linear_scan_range_bytes = total_data_blocks * self.block_size_bytes
        return {
            "branching_factor": node_capacity,
            "btree_height": btree_height,
            "btree_point_hops": btree_point_hops,
            "btree_point_bytes_read": btree_point_bytes,
            "btree_range_hops": btree_range_hops,
            "btree_range_bytes_read": btree_range_bytes,
            "linear_scan_point_hops": linear_scan_point_hops,
            "linear_scan_point_bytes_read": linear_scan_point_bytes,
            "linear_scan_range_hops": linear_scan_range_hops,
            "linear_scan_range_bytes_read": linear_scan_range_bytes,
            "total_data_blocks": total_data_blocks
        }
