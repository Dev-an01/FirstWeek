"""
Performance Metrics Tracking
=============================

Tracks performance metrics for the hybrid retrieval system:
- Latency percentiles (P50, P90, P95, P99)
- Strategy distribution
- Source contribution percentages
- Cache hit rates
- Error rates
"""

import time
from typing import Dict, List, Optional
from collections import defaultdict
import statistics


class PerformanceMetrics:
    """Track and report performance metrics"""
    
    def __init__(self):
        self.latencies: List[float] = []
        self.strategy_counts: Dict[str, int] = defaultdict(int)
        self.source_counts: Dict[str, int] = defaultdict(int)
        self.cache_hits: int = 0
        self.cache_misses: int = 0
        self.errors: int = 0
        self.total_queries: int = 0
        
    def record_query(
        self,
        latency_ms: float,
        strategy: str,
        sources: List[str],
        cache_hit: bool = False,
        error: bool = False
    ):
        """Record metrics for a single query"""
        self.total_queries += 1
        self.latencies.append(latency_ms)
        self.strategy_counts[strategy] += 1
        
        for source in sources:
            self.source_counts[source] += 1
        
        if cache_hit:
            self.cache_hits += 1
        else:
            self.cache_misses += 1
        
        if error:
            self.errors += 1
    
    def get_latency_percentiles(self) -> Dict[str, float]:
        """Calculate latency percentiles"""
        if not self.latencies:
            return {"P50": 0.0, "P90": 0.0, "P95": 0.0, "P99": 0.0}
        
        sorted_latencies = sorted(self.latencies)
        n = len(sorted_latencies)
        
        return {
            "P50": sorted_latencies[int(n * 0.50)],
            "P90": sorted_latencies[int(n * 0.90)],
            "P95": sorted_latencies[int(n * 0.95)],
            "P99": sorted_latencies[min(int(n * 0.99), n - 1)]
        }
    
    def get_cache_stats(self) -> Dict[str, float]:
        """Calculate cache statistics"""
        total = self.cache_hits + self.cache_misses
        if total == 0:
            return {"hit_rate": 0.0, "hits": 0, "misses": 0}
        
        return {
            "hit_rate": self.cache_hits / total,
            "hits": self.cache_hits,
            "misses": self.cache_misses
        }
    
    def get_strategy_distribution(self) -> Dict[str, float]:
        """Calculate strategy usage percentages"""
        if self.total_queries == 0:
            return {}
        
        return {
            strategy: count / self.total_queries
            for strategy, count in self.strategy_counts.items()
        }
    
    def get_source_contribution(self) -> Dict[str, float]:
        """Calculate source contribution percentages"""
        total = sum(self.source_counts.values())
        if total == 0:
            return {}
        
        return {
            source: count / total
            for source, count in self.source_counts.items()
        }
    
    def get_error_rate(self) -> float:
        """Calculate error rate"""
        if self.total_queries == 0:
            return 0.0
        return self.errors / self.total_queries
    
    def get_summary(self) -> Dict:
        """Get comprehensive metrics summary"""
        percentiles = self.get_latency_percentiles()
        cache_stats = self.get_cache_stats()
        
        return {
            "total_queries": self.total_queries,
            "latency": {
                **percentiles,
                "mean": statistics.mean(self.latencies) if self.latencies else 0.0,
                "median": statistics.median(self.latencies) if self.latencies else 0.0
            },
            "cache": cache_stats,
            "strategies": self.get_strategy_distribution(),
            "sources": self.get_source_contribution(),
            "error_rate": self.get_error_rate()
        }
    
    def print_report(self):
        """Print formatted metrics report"""
        summary = self.get_summary()
        
        print("\n" + "=" * 70)
        print("PERFORMANCE METRICS REPORT")
        print("=" * 70)
        
        print(f"\n📊 Total Queries: {summary['total_queries']}")
        
        print("\n⏱️  Latency Percentiles (ms):")
        for percentile, value in summary['latency'].items():
            if percentile in ['P50', 'P90', 'P95', 'P99']:
                print(f"  {percentile}: {value:,.0f} ms")
        print(f"  Mean: {summary['latency']['mean']:,.0f} ms")
        print(f"  Median: {summary['latency']['median']:,.0f} ms")
        
        if summary['cache']['hits'] + summary['cache']['misses'] > 0:
            print("\n💾 Cache Performance:")
            print(f"  Hit Rate: {summary['cache']['hit_rate']:.1%}")
            print(f"  Hits: {summary['cache']['hits']}")
            print(f"  Misses: {summary['cache']['misses']}")
        
        if summary['strategies']:
            print("\n🎯 Strategy Distribution:")
            for strategy, percentage in sorted(
                summary['strategies'].items(), 
                key=lambda x: x[1], 
                reverse=True
            ):
                print(f"  {strategy}: {percentage:.1%}")
        
        if summary['sources']:
            print("\n📚 Source Contribution:")
            for source, percentage in sorted(
                summary['sources'].items(), 
                key=lambda x: x[1], 
                reverse=True
            ):
                print(f"  {source}: {percentage:.1%}")
        
        if summary['error_rate'] > 0:
            print(f"\n❌ Error Rate: {summary['error_rate']:.1%}")
        
        print("\n" + "=" * 70)
    
    def reset(self):
        """Reset all metrics"""
        self.latencies = []
        self.strategy_counts = defaultdict(int)
        self.source_counts = defaultdict(int)
        self.cache_hits = 0
        self.cache_misses = 0
        self.errors = 0
        self.total_queries = 0
