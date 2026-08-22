from app.engines.dbms_engine.btree_simulator import BTreeSimulator
from app.engines.dbms_engine.cost_model import DBMSSimulationCostModel

def test_btree_height_calculation():
    btree = BTreeSimulator(block_size_bytes=4096, key_size_bytes=16, pointer_size_bytes=8)
    metrics = btree.calculate_metrics(num_records=1000)
    assert metrics["branching_factor"] == 171
    assert metrics["btree_height"] == 2
      
def test_cost_calculation():
    cost_model = DBMSSimulationCostModel(disk_seek_ms=10.0, cpu_latency_ms=1.0)
    cost = cost_model.calculate_cost(hops=3, bytes_read=12288, cache_hit_ratio=0.0)
    assert cost["cpu_latency_ms"] == 3.0
    assert cost["estimated_latency_ms"] >= 33.0
