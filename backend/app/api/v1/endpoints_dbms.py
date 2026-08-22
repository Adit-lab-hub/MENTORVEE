from fastapi import APIRouter, HTTPException
from app.schemas.dbms_schemas import DBMSQueryRequest, DBMSSimulationResult
from app.engines.dbms_engine.btree_simulator import BTreeSimulator
from app.engines.dbms_engine.cost_model import DBMSSimulationCostModel

router = APIRouter()

@router.post("/query", response_model=DBMSSimulationResult)
def query_dbms(payload: DBMSQueryRequest):
    try:
        btree_sim = BTreeSimulator(
            block_size_bytes=payload.config.block_size_bytes,
            record_size_bytes=128
        )
        metrics = btree_sim.calculate_metrics(payload.num_records, payload.range_fraction)
        cost_model = DBMSSimulationCostModel(
            disk_seek_ms=0.1 if payload.config.storage_type == "SSD" else 8.0,
            disk_transfer_mbps=100.0,
            cpu_latency_ms=0.05
        )
        is_seq = (payload.query_type != "point")
        if payload.config.index_type == "B-Tree":
            hops = metrics["btree_point_hops"] if payload.query_type == "point" else metrics["btree_range_hops"]
            bytes_read = metrics["btree_point_bytes_read"] if payload.query_type == "point" else metrics["btree_range_bytes_read"]
        else:
            hops = metrics["linear_scan_point_hops"] if payload.query_type == "point" else metrics["linear_scan_range_hops"]
            bytes_read = metrics["linear_scan_point_bytes_read"] if payload.query_type == "point" else metrics["linear_scan_range_bytes_read"]
            is_seq = True
            
        cost = cost_model.calculate_cost(
            hops=hops,
            bytes_read=bytes_read,
            is_sequential=is_seq,
            cache_hit_ratio=float(payload.config.buffer_pool_size / 200.0),
            concurrent_requests=payload.concurrent_requests,
            pool_size=payload.config.pool_size
        )
        warnings = []
        if cost["concurrency_pool_wait_ms"] > 20.0:
            warnings.append("Connection pool saturation detected: High queue time.")
        return {
            "estimated_latency_ms": cost["estimated_latency_ms"],
            "disk_iops": cost["disk_iops"],
            "cache_hit_ratio": min(1.0, float(payload.config.buffer_pool_size / 200.0)),
            "cpu_utilization": cost["cpu_utilization"],
            "btree_height": metrics["btree_height"],
            "node_hops": hops,
            "bytes_read": bytes_read,
            "concurrency_pool_wait_ms": cost["concurrency_pool_wait_ms"],
            "warnings": warnings
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
