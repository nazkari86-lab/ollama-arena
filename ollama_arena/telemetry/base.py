"""Hardware telemetry base interface and storage.

Provides unified telemetry collection interface, platform-specific hardware detection,
and telemetry storage/aggregation capabilities.
"""
from __future__ import annotations

import contextlib
import platform
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Iterator, List, Optional, Protocol, runtime_checkable


class HardwarePlatform(Enum):
    """Supported hardware platforms."""
    NVIDIA = "nvidia"
    AMD = "amd"
    APPLE = "apple"
    CPU = "cpu"
    UNKNOWN = "unknown"


@dataclass
class HardwareInfo:
    """Hardware platform information."""
    platform: HardwarePlatform
    device_name: str = ""
    device_id: str = ""
    total_memory_gb: float = 0.0
    compute_capability: str = ""
    driver_version: str = ""
    architecture: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "platform": self.platform.value,
            "device_name": self.device_name,
            "device_id": self.device_id,
            "total_memory_gb": self.total_memory_gb,
            "compute_capability": self.compute_capability,
            "driver_version": self.driver_version,
            "architecture": self.architecture,
        }


@dataclass
class TelemetryRecord:
    """Single telemetry measurement record."""
    timestamp: float
    model: str
    backend: str
    
    # Performance metrics
    tokens_in: int = 0
    tokens_out: int = 0
    latency_s: float = 0.0
    tps: float = 0.0
    time_to_first: float = 0.0
    
    # Energy metrics
    power_w: float = 0.0
    energy_j: float = 0.0
    tokens_per_watt: float = 0.0
    
    # Memory metrics
    memory_used_gb: float = 0.0
    memory_bandwidth_gb_s: float = 0.0
    
    # Context
    category: str = ""
    quantization: str = ""
    hardware_info: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "timestamp": self.timestamp,
            "model": self.model,
            "backend": self.backend,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "latency_s": self.latency_s,
            "tps": self.tps,
            "time_to_first": self.time_to_first,
            "power_w": self.power_w,
            "energy_j": self.energy_j,
            "tokens_per_watt": self.tokens_per_watt,
            "memory_used_gb": self.memory_used_gb,
            "memory_bandwidth_gb_s": self.memory_bandwidth_gb_s,
            "category": self.category,
            "quantization": self.quantization,
            "hardware_info": self.hardware_info,
        }


@runtime_checkable
class TelemetryStorage(Protocol):
    """Protocol for telemetry storage backends."""
    
    def store(self, record: TelemetryRecord) -> None:
        """Store a telemetry record."""
        ...
    
    def query(self, 
              model: Optional[str] = None,
              start_time: Optional[float] = None,
              end_time: Optional[float] = None,
              limit: int = 100) -> List[TelemetryRecord]:
        """Query telemetry records with filters."""
        ...
    
    def aggregate(self, 
                  model: Optional[str] = None,
                  group_by: str = "model") -> Dict[str, Any]:
        """Aggregate telemetry records."""
        ...
    
    def get_hardware_summary(self) -> Dict[str, Any]:
        """Get summary of hardware configurations."""
        ...


class SQLiteTelemetryStorage:
    """SQLite-based telemetry storage implementation."""
    
    def __init__(self, db_path: str = "arena.db"):
        """Initialize telemetry storage.
        
        Args:
            db_path: Path to SQLite database file.
        """
        self.db_path = db_path
        self._init_db()
    
    @contextlib.contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        """Get a database connection as a context manager.

        Opens a fresh connection, commits/rolls back on exit (matching
        sqlite3.Connection's own context-manager semantics), and always
        closes the connection afterward so callers don't leak file handles.
        """
        cx = sqlite3.connect(self.db_path)
        try:
            with cx:
                yield cx
        finally:
            cx.close()
    
    def _init_db(self) -> None:
        """Initialize telemetry tables."""
        with self._conn() as cx:
            cx.executescript("""
                CREATE TABLE IF NOT EXISTS telemetry_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    model TEXT NOT NULL,
                    backend TEXT NOT NULL,
                    tokens_in INTEGER DEFAULT 0,
                    tokens_out INTEGER DEFAULT 0,
                    latency_s REAL DEFAULT 0.0,
                    tps REAL DEFAULT 0.0,
                    time_to_first REAL DEFAULT 0.0,
                    power_w REAL DEFAULT 0.0,
                    energy_j REAL DEFAULT 0.0,
                    tokens_per_watt REAL DEFAULT 0.0,
                    memory_used_gb REAL DEFAULT 0.0,
                    memory_bandwidth_gb_s REAL DEFAULT 0.0,
                    category TEXT DEFAULT '',
                    quantization TEXT DEFAULT '',
                    hardware_info TEXT DEFAULT '{}',
                    hardware_platform TEXT DEFAULT 'unknown',
                    device_name TEXT DEFAULT ''
                );
                
                CREATE INDEX IF NOT EXISTS telemetry_model ON telemetry_records(model);
                CREATE INDEX IF NOT EXISTS telemetry_timestamp ON telemetry_records(timestamp);
                CREATE INDEX IF NOT EXISTS telemetry_platform ON telemetry_records(hardware_platform);
                
                CREATE TABLE IF NOT EXISTS hardware_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL,
                    device_name TEXT NOT NULL,
                    device_id TEXT NOT NULL,
                    total_memory_gb REAL DEFAULT 0.0,
                    compute_capability TEXT DEFAULT '',
                    driver_version TEXT DEFAULT '',
                    architecture TEXT DEFAULT '',
                    first_seen REAL NOT NULL,
                    last_seen REAL NOT NULL,
                    UNIQUE(platform, device_id)
                );
                
                CREATE INDEX IF NOT EXISTS hardware_platform_idx ON hardware_configs(platform);
            """)
    
    def store(self, record: TelemetryRecord) -> None:
        """Store a telemetry record."""
        import json
        
        hardware_platform = record.hardware_info.get("platform", "unknown")
        device_name = record.hardware_info.get("device_name", "")
        
        with self._conn() as cx:
            # Store telemetry record
            cx.execute("""
                INSERT INTO telemetry_records (
                    timestamp, model, backend, tokens_in, tokens_out,
                    latency_s, tps, time_to_first, power_w, energy_j,
                    tokens_per_watt, memory_used_gb, memory_bandwidth_gb_s,
                    category, quantization, hardware_info, hardware_platform, device_name
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.timestamp, record.model, record.backend,
                record.tokens_in, record.tokens_out, record.latency_s,
                record.tps, record.time_to_first, record.power_w,
                record.energy_j, record.tokens_per_watt,
                record.memory_used_gb, record.memory_bandwidth_gb_s,
                record.category, record.quantization,
                json.dumps(record.hardware_info),
                hardware_platform, device_name
            ))
            
            # Update hardware config
            if device_name:
                self._update_hardware_config(cx, record.hardware_info, record.timestamp)
    
    def _update_hardware_config(self, cx: sqlite3.Connection, 
                               hw_info: Dict[str, Any], timestamp: float) -> None:
        """Update or insert hardware configuration."""
        platform = hw_info.get("platform", "unknown")
        device_name = hw_info.get("device_name", "")
        device_id = hw_info.get("device_id", "")
        
        cx.execute("""
            INSERT OR REPLACE INTO hardware_configs (
                platform, device_name, device_id, total_memory_gb,
                compute_capability, driver_version, architecture,
                first_seen, last_seen
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 
                COALESCE((SELECT first_seen FROM hardware_configs 
                         WHERE platform=? AND device_id=?), ?),
                ?
            )
        """, (
            platform, device_name, device_id,
            hw_info.get("total_memory_gb", 0.0),
            hw_info.get("compute_capability", ""),
            hw_info.get("driver_version", ""),
            hw_info.get("architecture", ""),
            platform, device_id, timestamp, timestamp
        ))
    
    def query(self, 
              model: Optional[str] = None,
              start_time: Optional[float] = None,
              end_time: Optional[float] = None,
              limit: int = 100) -> List[TelemetryRecord]:
        """Query telemetry records with filters."""
        import json
        
        query = "SELECT * FROM telemetry_records WHERE 1=1"
        params = []
        
        if model:
            query += " AND model = ?"
            params.append(model)
        
        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)
        
        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        with self._conn() as cx:
            rows = cx.execute(query, params).fetchall()
        
        records = []
        for row in rows:
            records.append(TelemetryRecord(
                timestamp=row[1],
                model=row[2],
                backend=row[3],
                tokens_in=row[4],
                tokens_out=row[5],
                latency_s=row[6],
                tps=row[7],
                time_to_first=row[8],
                power_w=row[9],
                energy_j=row[10],
                tokens_per_watt=row[11],
                memory_used_gb=row[12],
                memory_bandwidth_gb_s=row[13],
                category=row[14],
                quantization=row[15],
                hardware_info=json.loads(row[16]) if row[16] else {}
            ))
        
        return records
    
    def aggregate(self, 
                  model: Optional[str] = None,
                  group_by: str = "model") -> Dict[str, Any]:
        """Aggregate telemetry records."""
        if group_by == "model":
            group_field = "model"
        elif group_by == "platform":
            group_field = "hardware_platform"
        elif group_by == "quantization":
            group_field = "quantization"
        else:
            group_field = "model"
        
        query = f"""
            SELECT {group_field}, 
                   COUNT(*) as count,
                   AVG(tokens_out) as avg_tokens,
                   AVG(latency_s) as avg_latency,
                   AVG(tps) as avg_tps,
                   AVG(time_to_first) as avg_ttft,
                   AVG(power_w) as avg_power,
                   AVG(energy_j) as avg_energy,
                   AVG(tokens_per_watt) as avg_tpw,
                   AVG(memory_used_gb) as avg_memory
            FROM telemetry_records
        """
        params = []
        
        if model:
            query += " WHERE model = ?"
            params.append(model)
        
        query += f" GROUP BY {group_field}"
        
        with self._conn() as cx:
            rows = cx.execute(query, params).fetchall()
        
        return {
            group_field: [
                {
                    "name": row[0],
                    "count": row[1],
                    "avg_tokens": round(row[2] or 0, 1),
                    "avg_latency": round(row[3] or 0, 2),
                    "avg_tps": round(row[4] or 0, 1),
                    "avg_ttft": round(row[5] or 0, 2),
                    "avg_power": round(row[6] or 0, 2),
                    "avg_energy": round(row[7] or 0, 2),
                    "avg_tpw": round(row[8] or 0, 1),
                    "avg_memory": round(row[9] or 0, 2),
                }
                for row in rows
            ]
        }
    
    def get_hardware_summary(self) -> Dict[str, Any]:
        """Get summary of hardware configurations."""
        with self._conn() as cx:
            rows = cx.execute("""
                SELECT platform, device_name, COUNT(*) as usage_count,
                       MIN(first_seen) as first_seen, MAX(last_seen) as last_seen
                FROM hardware_configs
                GROUP BY platform, device_name
            """).fetchall()
        
        return {
            "hardware": [
                {
                    "platform": row[0],
                    "device_name": row[1],
                    "usage_count": row[2],
                    "first_seen": datetime.fromtimestamp(row[3]).isoformat() if row[3] else None,
                    "last_seen": datetime.fromtimestamp(row[4]).isoformat() if row[4] else None,
                }
                for row in rows
            ]
        }


class HardwareDetector:
    """Detect available hardware and platform capabilities."""
    
    @staticmethod
    def detect_platform() -> HardwarePlatform:
        """Detect the hardware platform."""
        system = platform.system()
        
        if system == "Darwin":
            # Check for Apple Silicon
            if platform.machine().startswith(("arm64", "arm")):
                return HardwarePlatform.APPLE
        
        # Try to detect NVIDIA
        if HardwareDetector._has_nvidia():
            return HardwarePlatform.NVIDIA
        
        # Try to detect AMD
        if HardwareDetector._has_amd():
            return HardwarePlatform.AMD
        
        return HardwarePlatform.CPU
    
    @staticmethod
    def _has_nvidia() -> bool:
        """Check if NVIDIA GPU is available."""
        try:
            import pynvml
            pynvml.nvmlInit()
            return True
        except (ImportError, Exception):
            return False
    
    @staticmethod
    def _has_amd() -> bool:
        """Check if AMD GPU is available."""
        try:
            # Check for ROCm presence
            import os
            rocm_path = os.path.join(os.environ.get("ROCM_PATH", "/opt/rocm"), "bin")
            return os.path.exists(rocm_path)
        except Exception:
            return False
    
    @staticmethod
    def get_hardware_info() -> HardwareInfo:
        """Get detailed hardware information."""
        hw_platform = HardwareDetector.detect_platform()
        
        if hw_platform == HardwarePlatform.NVIDIA:
            return HardwareDetector._get_nvidia_info()
        elif hw_platform == HardwarePlatform.APPLE:
            return HardwareDetector._get_apple_info()
        elif hw_platform == HardwarePlatform.AMD:
            return HardwareDetector._get_amd_info()
        else:
            return HardwareInfo(
                platform=HardwarePlatform.CPU,
                device_name=platform.processor(),
                architecture=platform.machine(),
            )
    
    @staticmethod
    def _get_nvidia_info() -> HardwareInfo:
        """Get NVIDIA GPU information."""
        try:
            import pynvml
            
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            
            name = pynvml.nvmlDeviceGetName(handle)
            memory_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            cc = pynvml.nvmlDeviceGetCudaComputeCapability(handle)
            driver_version = pynvml.nvmlSystemGetDriverVersion()
            
            return HardwareInfo(
                platform=HardwarePlatform.NVIDIA,
                device_name=name.decode() if isinstance(name, bytes) else name,
                device_id="gpu:0",
                total_memory_gb=memory_info.total / (1024**3),
                compute_capability=f"{cc.major}.{cc.minor}",
                driver_version=driver_version.decode() if isinstance(driver_version, bytes) else driver_version,
                architecture="cuda",
            )
        except Exception:
            return HardwareInfo(
                platform=HardwarePlatform.NVIDIA,
                device_name="Unknown NVIDIA GPU",
                device_id="gpu:0",
            )
    
    @staticmethod
    def _get_apple_info() -> HardwareInfo:
        """Get Apple Silicon GPU information."""
        try:
            import subprocess
            
            # Get GPU info from system_profiler on macOS
            result = subprocess.run(
                ["system_profiler", "SPDisplaysDataType"],
                capture_output=True, text=True
            )
            
            device_name = "Apple Silicon GPU"
            total_memory_gb = 0.0
            
            if result.returncode == 0:
                output = result.stdout
                if "Chipset Model" in output:
                    for line in output.split("\n"):
                        if "Chipset Model" in line:
                            device_name = line.split(":")[1].strip()
                        if "VRAM" in line:
                            try:
                                vram_gb = float(line.split(":")[1].strip().replace(" GB", ""))
                                total_memory_gb = vram_gb
                            except Exception:
                                pass
            
            return HardwareInfo(
                platform=HardwarePlatform.APPLE,
                device_name=device_name,
                device_id="apple-gpu:0",
                total_memory_gb=total_memory_gb,
                architecture="apple-silicon",
            )
        except Exception:
            return HardwareInfo(
                platform=HardwarePlatform.APPLE,
                device_name="Apple Silicon GPU",
                device_id="apple-gpu:0",
                architecture="apple-silicon",
            )
    
    @staticmethod
    def _get_amd_info() -> HardwareInfo:
        """Get AMD GPU information."""
        try:
            import subprocess
            
            # Try to get AMD GPU info via rocm-smi
            result = subprocess.run(
                ["rocm-smi", "--showproductname"],
                capture_output=True, text=True
            )
            
            device_name = "AMD GPU"
            total_memory_gb = 0.0
            
            if result.returncode == 0:
                output = result.stdout
                # Parse rocm-smi output
                for line in output.split("\n"):
                    if "GPU" in line and "Card series" in line:
                        device_name = line.strip()
            
            return HardwareInfo(
                platform=HardwarePlatform.AMD,
                device_name=device_name,
                device_id="amd-gpu:0",
                total_memory_gb=total_memory_gb,
                architecture="rocm",
            )
        except Exception:
            return HardwareInfo(
                platform=HardwarePlatform.AMD,
                device_name="AMD GPU",
                device_id="amd-gpu:0",
                architecture="rocm",
            )


@runtime_checkable
class TelemetryCollector(Protocol):
    """Protocol for telemetry collectors."""
    
    def start_recording(self, model: str, backend: str) -> None:
        """Start recording telemetry for a generation."""
        ...
    
    def stop_recording(self) -> TelemetryRecord:
        """Stop recording and return the telemetry record."""
        ...
    
    def record_generation(self, record: TelemetryRecord) -> None:
        """Record a completed generation."""
        ...
    
    def get_current_hardware(self) -> HardwareInfo:
        """Get current hardware information."""
        ...


class BaseTelemetryCollector:
    """Base implementation of telemetry collector."""
    
    def __init__(self, storage: Optional[TelemetryStorage] = None):
        """Initialize telemetry collector.
        
        Args:
            storage: Telemetry storage backend. If None, uses SQLite.
        """
        self.storage = storage or SQLiteTelemetryStorage()
        self.hardware_info = HardwareDetector.get_hardware_info()
        self._recording_start: Optional[float] = None
        self._current_model: Optional[str] = None
        self._current_backend: Optional[str] = None
    
    def start_recording(self, model: str, backend: str) -> None:
        """Start recording telemetry for a generation."""
        self._recording_start = time.time()
        self._current_model = model
        self._current_backend = backend
    
    def stop_recording(self, tokens_in: int = 0, tokens_out: int = 0,
                      latency_s: float = 0.0, tps: float = 0.0,
                      time_to_first: float = 0.0, category: str = "",
                      quantization: str = "") -> TelemetryRecord:
        """Stop recording and return the telemetry record."""
        if self._recording_start is None:
            raise RuntimeError("Recording not started")
        
        record = TelemetryRecord(
            timestamp=time.time(),
            model=self._current_model or "unknown",
            backend=self._current_backend or "unknown",
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_s=latency_s,
            tps=tps,
            time_to_first=time_to_first,
            category=category,
            quantization=quantization,
            hardware_info=self.hardware_info.to_dict(),
        )
        
        self._recording_start = None
        self._current_model = None
        self._current_backend = None
        
        return record
    
    def record_generation(self, record: TelemetryRecord) -> None:
        """Record a completed generation."""
        self.storage.store(record)
    
    def get_current_hardware(self) -> HardwareInfo:
        """Get current hardware information."""
        return self.hardware_info


def get_telemetry_collector(storage: Optional[TelemetryStorage] = None,
                           db_path: str = "arena.db") -> BaseTelemetryCollector:
    """Factory function to get a telemetry collector instance.
    
    Args:
        storage: Custom storage backend. If None, uses SQLite.
        db_path: Path to SQLite database (only used if storage is None).
    
    Returns:
        TelemetryCollector instance.
    """
    if storage is None:
        storage = SQLiteTelemetryStorage(db_path)
    
    return BaseTelemetryCollector(storage)
