from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
import json
from typing import List

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        await websocket.send_json(message)

manager = ConnectionManager()

@router.websocket("/telemetry")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    cpu_load = 10.0
    memory_pressure = 20.0
    latency_ms = 2.0
    dropped_connections = 0
    chaos_active = False
    chaos_type = ""
    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=0.5)
                payload = json.loads(data)
                if payload.get("type") == "chaos":
                    chaos_active = True
                    chaos_type = payload.get("event", "disk_latency_spike")
                elif payload.get("type") == "reset":
                    chaos_active = False
                    chaos_type = ""
                    cpu_load = 10.0
                    memory_pressure = 20.0
                    latency_ms = 2.0
                    dropped_connections = 0
            except asyncio.TimeoutError:
                pass
            if chaos_active:
                if chaos_type == "disk_latency_spike":
                    latency_ms = min(500.0, latency_ms + 45.0)
                    cpu_load = min(100.0, cpu_load + 2.0)
                elif chaos_type == "thrashing":
                    memory_pressure = min(100.0, memory_pressure + 15.0)
                    if memory_pressure > 80.0:
                        latency_ms = min(1000.0, latency_ms + 120.0)
                        cpu_load = max(5.0, cpu_load - 10.0)
                elif chaos_type == "connection_depletion":
                    dropped_connections += 2
                    latency_ms = min(2000.0, latency_ms + 250.0)
            else:
                cpu_load = max(10.0, cpu_load - 5.0)
                memory_pressure = max(20.0, memory_pressure - 10.0)
                latency_ms = max(2.0, latency_ms - 20.0)
                dropped_connections = max(0, dropped_connections - 1)
            telemetry = {
                "cpu_load": round(cpu_load, 2),
                "memory_pressure": round(memory_pressure, 2),
                "latency_ms": round(latency_ms, 2),
                "dropped_connections": dropped_connections,
                "chaos_active": chaos_active,
                "chaos_type": chaos_type
            }
            await manager.send_personal_message(telemetry, websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
