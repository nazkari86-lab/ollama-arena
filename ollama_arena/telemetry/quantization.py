"""Optimal quantization discovery and analysis.

Implements automated testing across model quantization variants,
Pareto frontier analysis (ELO degradation vs VRAM savings), and
recommendation engine for optimal format per hardware.
"""
from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Any, Optional

from .base import HardwareInfo, HardwareDetector


class QuantizationFormat(Enum):
    """Supported quantization formats."""
    Q4_K_M = "Q4_K_M"
    Q4_K_S = "Q4_K_S"
    Q5_K_M = "Q5_K_M"
    Q5_K_S = "Q5_K_S"
    Q8_0 = "Q8_0"
    FP16 = "FP16"
    FP32 = "FP32"
    IQ4_NL = "IQ4_NL"
    IQ4_XS = "IQ4_XS"


@dataclass
class QuantizationResult:
    """Results from testing a specific quantization."""
    format: QuantizationFormat
    model_name: str
    file_size_gb: float
    vram_usage_gb: float
    
    # Performance metrics
    avg_latency_s: float = 0.0
    avg_tps: float = 0.0
    avg_ttft_s: float = 0.0
    
    # Quality metrics
    elo_score: float = 0.0
    quality_score: float = 0.0
    
    # Energy metrics
    avg_power_w: float = 0.0
    tokens_per_watt: float = 0.0
    
    # Test metadata
    test_duration_s: float = 0.0
    num_samples: int = 0
    error: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "format": self.format.value,
            "model_name": self.model_name,
            "file_size_gb": self.file_size_gb,
            "vram_usage_gb": self.vram_usage_gb,
            "avg_latency_s": self.avg_latency_s,
            "avg_tps": self.avg_tps,
            "avg_ttft_s": self.avg_ttft_s,
            "elo_score": self.elo_score,
            "quality_score": self.quality_score,
            "avg_power_w": self.avg_power_w,
            "tokens_per_watt": self.tokens_per_watt,
            "test_duration_s": self.test_duration_s,
            "num_samples": self.num_samples,
            "error": self.error,
        }


@dataclass
class ParetoPoint:
    """A point on the Pareto frontier."""
    format: QuantizationFormat
    elo_score: float
    vram_savings_gb: float
    efficiency_score: float
    is_pareto_optimal: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "format": self.format.value,
            "elo_score": self.elo_score,
            "vram_savings_gb": self.vram_savings_gb,
            "efficiency_score": self.efficiency_score,
            "is_pareto_optimal": self.is_pareto_optimal,
        }


class ParetoFrontier:
    """Pareto frontier analysis for quantization trade-offs."""
    
    def __init__(self, results: List[QuantizationResult]):
        """Initialize Pareto frontier analysis.
        
        Args:
            results: List of quantization test results.
        """
        self.results = results
        self.frontier: List[ParetoPoint] = []
        self._analyze()
    
    def _analyze(self) -> None:
        """Perform Pareto frontier analysis."""
        if not self.results:
            return
        
        # Find baseline (FP16 or largest format)
        baseline = max(self.results, key=lambda r: r.elo_score)
        
        # Create points
        points = []
        for result in self.results:
            vram_savings = baseline.vram_usage_gb - result.vram_usage_gb
            elo_degradation = baseline.elo_score - result.elo_score
            
            # Efficiency score: VRAM savings per ELO point lost
            if elo_degradation > 0:
                efficiency = vram_savings / elo_degradation
            else:
                # No ELO loss, so efficiency is high
                efficiency = vram_savings * 10 if vram_savings > 0 else 0
            
            points.append(ParetoPoint(
                format=result.format,
                elo_score=result.elo_score,
                vram_savings_gb=vram_savings,
                efficiency_score=efficiency,
            ))
        
        # Find Pareto optimal points
        # Sort by ELO score descending
        points.sort(key=lambda p: p.elo_score, reverse=True)
        
        # A point is Pareto optimal if no other point has both higher ELO and higher VRAM savings
        for i, point in enumerate(points):
            is_optimal = True
            for other in points:
                if (other.elo_score >= point.elo_score and 
                    other.vram_savings_gb >= point.vram_savings_gb and
                    (other.elo_score > point.elo_score or other.vram_savings_gb > point.vram_savings_gb)):
                    is_optimal = False
                    break
            
            point.is_pareto_optimal = is_optimal
        
        self.frontier = [p for p in points if p.is_pareto_optimal]
    
    def get_optimal_format(self, 
                          max_vram_gb: Optional[float] = None,
                          min_elo: Optional[float] = None) -> Optional[QuantizationFormat]:
        """Get optimal quantization format based on constraints.
        
        Args:
            max_vram_gb: Maximum VRAM constraint.
            min_elo: Minimum ELO score constraint.
        
        Returns:
            Optimal quantization format or None if no format meets constraints.
        """
        candidates = self.frontier

        if max_vram_gb is not None:
            # Convert to VRAM usage from savings
            baseline = max(self.results, key=lambda r: r.elo_score)
            candidates = [p for p in candidates
                         if (baseline.vram_usage_gb - p.vram_savings_gb) <= max_vram_gb]

        if min_elo is not None:
            candidates = [p for p in candidates if p.elo_score >= min_elo]
        
        if not candidates:
            return None
        
        # Return the most efficient option
        return max(candidates, key=lambda p: p.efficiency_score).format
    
    def get_recommendations(self, hardware: HardwareInfo) -> Dict[str, QuantizationFormat]:
        """Get format recommendations for different use cases.
        
        Args:
            hardware: Hardware information.
        
        Returns:
            Dictionary mapping use case to recommended format.
        """
        recommendations = {}
        
        if not self.frontier:
            return recommendations
        
        # High-end GPU: prioritize quality
        if hardware.total_memory_gb >= 24:
            recommendations["quality"] = max(self.frontier, key=lambda p: p.elo_score).format
        # Mid-range GPU: balance
        elif hardware.total_memory_gb >= 12:
            recommendations["balanced"] = max(self.frontier, key=lambda p: p.efficiency_score).format
        # Low-end GPU: prioritize VRAM
        else:
            recommendations["vram_optimized"] = max(self.frontier, key=lambda p: p.vram_savings_gb).format
        
        # Energy-efficient: prioritize tokens-per-watt
        energy_candidates = [r for r in self.results if r.tokens_per_watt > 0]
        if energy_candidates:
            best_energy = max(energy_candidates, key=lambda r: r.tokens_per_watt)
            recommendations["energy_efficient"] = best_energy.format
        
        return recommendations
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "frontier": [p.to_dict() for p in self.frontier],
            "all_points": [p.to_dict() for p in [
                ParetoPoint(
                    format=r.format,
                    elo_score=r.elo_score,
                    vram_savings_gb=max(self.results, key=lambda x: x.elo_score).vram_usage_gb - r.vram_usage_gb,
                    efficiency_score=0.0,
                )
                for r in self.results
            ]],
        }


class QuantizationTester:
    """Automated quantization testing system."""
    
    def __init__(self, 
                 backend_url: str = "http://localhost:11434",
                 hardware: Optional[HardwareInfo] = None):
        """Initialize quantization tester.
        
        Args:
            backend_url: URL to model backend (e.g., Ollama).
            hardware: Hardware information. If None, auto-detected.
        """
        self.backend_url = backend_url
        self.hardware = hardware or HardwareDetector.get_hardware_info()
        self.results: List[QuantizationResult] = []
    
    def list_available_formats(self, model_name: str) -> List[QuantizationFormat]:
        """List available quantization formats for a model.
        
        Args:
            model_name: Base model name (e.g., "llama2").
        
        Returns:
            List of available quantization formats.
        """
        available = []
        
        try:
            # Query Ollama for available models
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                # Parse output for model variants
                for line in result.stdout.split("\n"):
                    if model_name.lower() in line.lower():
                        for fmt in QuantizationFormat:
                            if fmt.value in line:
                                available.append(fmt)
        except Exception:
            # Fallback: assume common formats are available
            available = [
                QuantizationFormat.Q4_K_M,
                QuantizationFormat.Q8_0,
                QuantizationFormat.FP16,
            ]
        
        # Remove duplicates
        return list(set(available))
    
    def download_model(self, model_name: str, format: QuantizationFormat) -> bool:
        """Download a specific quantization of a model.
        
        Args:
            model_name: Base model name.
            format: Quantization format to download.
        
        Returns:
            True if download succeeded.
        """
        full_name = f"{model_name}:{format.value.lower()}"
        
        try:
            result = subprocess.run(
                ["ollama", "pull", full_name],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            return result.returncode == 0
        except Exception:
            return False
    
    def get_model_size(self, model_name: str, format: QuantizationFormat) -> float:
        """Get model file size in GB.
        
        Args:
            model_name: Base model name.
            format: Quantization format.
        
        Returns:
            File size in GB.
        """
        full_name = f"{model_name}:{format.value.lower()}"
        
        try:
            # Use ollama show to get model info
            result = subprocess.run(
                ["ollama", "show", full_name, "--modelfile"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                # Parse modelfile for size information
                # This is approximate; actual size depends on quantization
                # Q4_K_M ~4 bits per param, Q8_0 ~8 bits, FP16 ~16 bits
                param_count = self._extract_param_count(result.stdout)
                
                # Calculate size based on format
                bits_per_param = {
                    QuantizationFormat.Q4_K_M: 4.5,
                    QuantizationFormat.Q4_K_S: 4.25,
                    QuantizationFormat.Q5_K_M: 5.5,
                    QuantizationFormat.Q5_K_S: 5.5,
                    QuantizationFormat.Q8_0: 8.0,
                    QuantizationFormat.FP16: 16.0,
                    QuantizationFormat.FP32: 32.0,
                }.get(format, 8.0)
                
                size_bytes = (param_count * bits_per_param) / 8
                return size_bytes / (1024**3)  # Convert to GB
        
        except Exception:
            pass
        
        # Fallback: estimate based on format
        size_estimates = {
            QuantizationFormat.Q4_K_M: 4.0,  # For 7B model
            QuantizationFormat.Q8_0: 7.0,
            QuantizationFormat.FP16: 14.0,
        }
        return size_estimates.get(format, 7.0)
    
    def _extract_param_count(self, modelfile: str) -> int:
        """Extract parameter count from modelfile.
        
        Args:
            modelfile: Model file content.
        
        Returns:
            Estimated parameter count.
        """
        # This is a simplified extraction
        # In practice, you'd parse the actual model metadata
        if "7B" in modelfile or "7b" in modelfile:
            return 7_000_000_000
        elif "13B" in modelfile or "13b" in modelfile:
            return 13_000_000_000
        elif "70B" in modelfile or "70b" in modelfile:
            return 70_000_000_000
        else:
            return 7_000_000_000  # Default assumption
    
    def test_quantization(self, 
                         model_name: str,
                         format: QuantizationFormat,
                         test_prompts: List[str],
                         num_samples: int = 10) -> QuantizationResult:
        """Test a specific quantization format.
        
        Args:
            model_name: Base model name.
            format: Quantization format to test.
            test_prompts: List of test prompts.
            num_samples: Number of test samples to run.
        
        Returns:
            QuantizationResult with performance metrics.
        """
        full_name = f"{model_name}:{format.value.lower()}"
        
        start_time = time.time()
        latencies = []
        tps_values = []
        ttft_values = []
        
        # Run test samples
        for i in range(min(num_samples, len(test_prompts))):
            prompt = test_prompts[i % len(test_prompts)]
            
            try:
                result = self._run_inference(full_name, prompt)
                
                if result:
                    latencies.append(result.get("latency_s", 0.0))
                    tps_values.append(result.get("tps", 0.0))
                    ttft_values.append(result.get("time_to_first", 0.0))
            except Exception as e:
                return QuantizationResult(
                    format=format,
                    model_name=model_name,
                    file_size_gb=self.get_model_size(model_name, format),
                    vram_usage_gb=0.0,
                    error=str(e),
                )
        
        duration = time.time() - start_time
        
        # Calculate averages
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
        avg_tps = sum(tps_values) / len(tps_values) if tps_values else 0.0
        avg_ttft = sum(ttft_values) / len(ttft_values) if ttft_values else 0.0
        
        # Estimate VRAM usage (simplified)
        vram_usage = self._estimate_vram_usage(model_name, format)
        
        return QuantizationResult(
            format=format,
            model_name=model_name,
            file_size_gb=self.get_model_size(model_name, format),
            vram_usage_gb=vram_usage,
            avg_latency_s=avg_latency,
            avg_tps=avg_tps,
            avg_ttft_s=avg_ttft,
            test_duration_s=duration,
            num_samples=len(latencies),
        )
    
    def _run_inference(self, model: str, prompt: str) -> Optional[Dict[str, float]]:
        """Run inference and return metrics.
        
        Args:
            model: Full model name with quantization.
            prompt: Test prompt.
        
        Returns:
            Dictionary with latency, tps, time_to_first.
        """
        try:
            start = time.time()
            result = subprocess.run(
                ["ollama", "run", model, prompt],
                capture_output=True,
                text=True,
                timeout=60
            )
            latency = time.time() - start
            
            if result.returncode == 0:
                # Estimate tokens from output length
                # This is approximate; actual tokenization varies
                output_tokens = len(result.stdout.split())
                
                return {
                    "latency_s": latency,
                    "tps": output_tokens / latency if latency > 0 else 0.0,
                    "time_to_first": latency * 0.1,  # Rough estimate
                }
        except Exception:
            pass
        
        return None
    
    def _estimate_vram_usage(self, model_name: str, format: QuantizationFormat) -> float:
        """Estimate VRAM usage for a quantization.
        
        Args:
            model_name: Base model name.
            format: Quantization format.
        
        Returns:
            Estimated VRAM usage in GB.
        """
        # Base model size estimation
        base_size = self._extract_param_count(model_name)
        
        # VRAM includes model weights + KV cache + overhead
        # Approximate: model size * 1.5 for runtime
        bits_per_param = {
            QuantizationFormat.Q4_K_M: 4.5,
            QuantizationFormat.Q8_0: 8.0,
            QuantizationFormat.FP16: 16.0,
        }.get(format, 8.0)
        
        model_size_gb = (base_size * bits_per_param / 8) / (1024**3)
        return model_size_gb * 1.5
    
    def run_full_test(self, 
                     model_name: str,
                     formats: Optional[List[QuantizationFormat]] = None,
                     test_prompts: Optional[List[str]] = None,
                     auto_download: bool = True) -> ParetoFrontier:
        """Run full quantization test suite.
        
        Args:
            model_name: Base model name.
            formats: List of formats to test. If None, uses available formats.
            test_prompts: Test prompts. If None, uses default prompts.
            auto_download: Whether to automatically download missing formats.
        
        Returns:
            ParetoFrontier analysis results.
        """
        if formats is None:
            formats = self.list_available_formats(model_name)
        
        if test_prompts is None:
            test_prompts = [
                "Explain quantum computing in simple terms.",
                "Write a Python function to sort a list.",
                "What is the capital of France?",
                "Summarize the main themes of Romeo and Juliet.",
                "Explain the difference between HTTP and HTTPS.",
            ]
        
        results = []
        
        for fmt in formats:
            if auto_download:
                if not self.download_model(model_name, fmt):
                    print(f"Failed to download {model_name}:{fmt.value.lower()}")
                    continue
            
            result = self.test_quantization(model_name, fmt, test_prompts)
            results.append(result)
            
            print(f"Tested {fmt.value}: TPS={result.avg_tps:.1f}, "
                  f"Latency={result.avg_latency_s:.2f}s, "
                  f"VRAM={result.vram_usage_gb:.1f}GB")
        
        self.results = results
        return ParetoFrontier(results)
    
    def get_optimal_for_hardware(self, 
                                model_name: str,
                                hardware: Optional[HardwareInfo] = None) -> Dict[str, Any]:
        """Get optimal quantization for specific hardware.
        
        Args:
            model_name: Base model name.
            hardware: Hardware info. If None, uses detected hardware.
        
        Returns:
            Dictionary with recommendations and analysis.
        """
        if hardware is None:
            hardware = self.hardware
        
        frontier = self.run_full_test(model_name, auto_download=False)
        recommendations = frontier.get_recommendations(hardware)
        
        return {
            "hardware": hardware.to_dict(),
            "recommendations": {k: v.value for k, v in recommendations.items()},
            "frontier": frontier.to_dict(),
        }


def get_quantization_tester(backend_url: str = "http://localhost:11434",
                           hardware: Optional[HardwareInfo] = None) -> QuantizationTester:
    """Factory function to get a quantization tester instance.
    
    Args:
        backend_url: URL to model backend.
        hardware: Hardware information.
    
    Returns:
        QuantizationTester instance.
    """
    return QuantizationTester(backend_url, hardware)
