"""
Cache Monitoring and Metrics Collection
===================================

Comprehensive monitoring system for cache performance:

Features:
- Real-time metrics collection
- Performance alerting
- Health monitoring
- Historical data tracking
- Automated reporting

Author: AI Officer Implementation Team
Date: 2025-10-30
"""

import time
import logging
import json
import asyncio
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from collections import defaultdict, deque

from .config import CACHE_MONITORING_CONFIG

logger = logging.getLogger(__name__)


@dataclass
class Alert:
    """Alert definition"""
    alert_type: str
    severity: str  # info, warning, error, critical
    message: str
    timestamp: float
    metrics: Dict[str, Any]
    resolved: bool = False
    resolution_time: Optional[float] = None


@dataclass
class MonitoringReport:
    """Monitoring report with metrics and alerts"""
    timestamp: float
    cache_health: Dict[str, Any]
    performance_metrics: Dict[str, Any]
    alerts: List[Alert]
    recommendations: List[str]


class CacheMonitor:
    """
    Comprehensive cache monitoring system
    
    Monitors:
    - Cache hit rates and performance
    - Memory usage and capacity
    - Error rates and latency
    - Health status changes
    """
    
    def __init__(self, cache_manager, alert_callbacks: List[Callable] = None):
        """
        Initialize cache monitor
        
        Args:
            cache_manager: Cache manager to monitor
            alert_callbacks: List of callback functions for alerts
        """
        self.cache_manager = cache_manager
        self.config = CACHE_MONITORING_CONFIG
        self.alert_callbacks = alert_callbacks or []
        
        # Monitoring state
        self.is_monitoring = False
        self.monitoring_task = None
        self.last_health_check = 0
        self.last_metrics_report = 0
        
        # Historical data
        self.metrics_history = deque(maxlen=1000)  # Last 1000 data points
        self.alert_history = deque(maxlen=100)  # Last 100 alerts
        
        # Alert thresholds
        self.alert_thresholds = {
            'hit_rate_low': self.config.get('hit_rate_alert_threshold', 0.50),
            'latency_high': self.config.get('latency_alert_threshold_ms', 100),
            'memory_high': self.config.get('memory_alert_threshold_gb', 1.5),
            'error_rate_high': 0.05  # 5% error rate
        }
        
        logger.info("CacheMonitor initialized")
    
    async def start_monitoring(self):
        """Start background monitoring"""
        if self.is_monitoring:
            logger.warning("Cache monitoring already started")
            return
        
        if not self.config.get('enabled', True):
            logger.info("Cache monitoring disabled in configuration")
            return
        
        self.is_monitoring = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        
        logger.info("Cache monitoring started")
    
    async def stop_monitoring(self):
        """Stop background monitoring"""
        if not self.is_monitoring:
            return
        
        self.is_monitoring = False
        
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Cache monitoring stopped")
    
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.is_monitoring:
            try:
                # Collect current metrics
                current_time = time.time()
                metrics = self.cache_manager.get_metrics()
                health = self.cache_manager.health_check()
                
                # Store in history
                self.metrics_history.append({
                    'timestamp': current_time,
                    'metrics': metrics,
                    'health': health
                })
                
                # Check for alerts
                alerts = self._check_alerts(metrics, health)
                
                # Store alerts
                for alert in alerts:
                    self.alert_history.append(alert)
                
                # Send alerts
                if alerts:
                    await self._send_alerts(alerts)
                
                # Periodic reporting
                if current_time - self.last_metrics_report >= self.config.get('metrics_report_interval_seconds', 300):
                    await self._generate_report()
                    self.last_metrics_report = current_time
                
                # Sleep until next check
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Cache monitoring error: {e}")
                await asyncio.sleep(60)  # Wait longer on error
    
    def _check_alerts(self, metrics: Dict[str, Any], health: Dict[str, Any]) -> List[Alert]:
        """Check for alert conditions"""
        alerts = []
        current_time = time.time()
        
        # Check hit rate alerts
        overall_hit_rate = metrics.get('overall_hit_rate', 0.0)
        if overall_hit_rate < self.alert_thresholds['hit_rate_low']:
            alerts.append(Alert(
                alert_type='hit_rate_low',
                severity='warning',
                message=f"Cache hit rate is low: {overall_hit_rate:.2%}",
                timestamp=current_time,
                metrics={'hit_rate': overall_hit_rate}
            ))
        
        # Check latency alerts
        avg_get_time = metrics.get('avg_get_time_ms', 0.0)
        if avg_get_time > self.alert_thresholds['latency_high']:
            alerts.append(Alert(
                alert_type='latency_high',
                severity='warning',
                message=f"Cache latency is high: {avg_get_time:.1f}ms",
                timestamp=current_time,
                metrics={'avg_get_time_ms': avg_get_time}
            ))
        
        # Check error rate alerts
        total_ops = metrics.get('total_requests', 0)
        total_errors = sum([
            metrics.get('semantic_query_metrics', {}).get('errors', 0),
            metrics.get('embedding_metrics', {}).get('errors', 0),
            metrics.get('system_prompt_metrics', {}).get('errors', 0)
        ])
        
        if total_ops > 0:
            error_rate = total_errors / total_ops
            if error_rate > self.alert_thresholds['error_rate_high']:
                alerts.append(Alert(
                    alert_type='error_rate_high',
                    severity='error',
                    message=f"Cache error rate is high: {error_rate:.2%}",
                    timestamp=current_time,
                    metrics={'error_rate': error_rate, 'total_errors': total_errors}
                ))
        
        # Check health status alerts
        if health.get('overall_status') == 'unhealthy':
            alerts.append(Alert(
                alert_type='health_unhealthy',
                severity='critical',
                message=f"Cache system is unhealthy: {health.get('issues', [])}",
                timestamp=current_time,
                metrics={'health_status': health}
            ))
        elif health.get('overall_status') == 'degraded':
            alerts.append(Alert(
                alert_type='health_degraded',
                severity='warning',
                message=f"Cache system is degraded: {health.get('issues', [])}",
                timestamp=current_time,
                metrics={'health_status': health}
            ))
        
        return alerts
    
    async def _send_alerts(self, alerts: List[Alert]):
        """Send alerts to configured callbacks"""
        for alert in alerts:
            logger.warning(f"Cache alert: {alert.message}")
            
            for callback in self.alert_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(alert)
                    else:
                        callback(alert)
                except Exception as e:
                    logger.error(f"Alert callback error: {e}")
    
    async def _generate_report(self):
        """Generate monitoring report"""
        current_time = time.time()
        
        # Get latest metrics and health
        latest_data = self.metrics_history[-1] if self.metrics_history else None
        if not latest_data:
            return
        
        metrics = latest_data['metrics']
        health = latest_data['health']
        
        # Generate recommendations
        recommendations = self._generate_recommendations(metrics, health)
        
        # Create report
        report = MonitoringReport(
            timestamp=current_time,
            cache_health=health,
            performance_metrics=metrics,
            alerts=list(self.alert_history)[-10:],  # Last 10 alerts
            recommendations=recommendations
        )
        
        # Log report
        logger.info(f"Cache monitoring report generated: {len(recommendations)} recommendations")
        
        # Store report (could be sent to external system)
        if self.config.get('detailed_logging', False):
            report_file = f"cache_report_{datetime.fromtimestamp(current_time).strftime('%Y%m%d_%H%M%S')}.json"
            with open(report_file, 'w') as f:
                json.dump(asdict(report), f, indent=2, default=str)
    
    def _generate_recommendations(self, metrics: Dict[str, Any], health: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on metrics and health"""
        recommendations = []
        
        # Hit rate recommendations
        overall_hit_rate = metrics.get('overall_hit_rate', 0.0)
        if overall_hit_rate < 0.7:
            recommendations.append("Consider cache warming for popular queries")
            recommendations.append("Review cache TTL settings for optimal hit rates")
        elif overall_hit_rate < 0.5:
            recommendations.append("Critical: Cache hit rate is very low, investigate cache key generation")
        
        # Latency recommendations
        avg_get_time = metrics.get('avg_get_time_ms', 0.0)
        if avg_get_time > 50:
            recommendations.append("Consider optimizing Redis connection pooling")
        if avg_get_time > 100:
            recommendations.append("High latency detected, check Redis server performance")
        
        # Error rate recommendations
        total_ops = metrics.get('total_requests', 0)
        total_errors = sum([
            metrics.get('semantic_query_metrics', {}).get('errors', 0),
            metrics.get('embedding_metrics', {}).get('errors', 0),
            metrics.get('system_prompt_metrics', {}).get('errors', 0)
        ])
        
        if total_ops > 0:
            error_rate = total_errors / total_ops
            if error_rate > 0.02:  # 2%
                recommendations.append("Investigate Redis connection stability")
            if error_rate > 0.05:  # 5%
                recommendations.append("Critical: High error rate, check Redis configuration")
        
        # Level-specific recommendations
        semantic_metrics = metrics.get('semantic_query_metrics', {})
        if semantic_metrics.get('hit_rate', 1.0) < 0.8:
            recommendations.append("Semantic query cache below target (85%), review query normalization")
        
        embedding_metrics = metrics.get('embedding_metrics', {})
        if embedding_metrics.get('overall_hit_rate', 1.0) < 0.7:
            recommendations.append("Embedding cache below target (70%), consider cache warming")
        
        system_prompt_metrics = metrics.get('system_prompt_metrics', {})
        if system_prompt_metrics.get('hit_rate', 1.0) < 0.9:
            recommendations.append("System prompt cache below target (90%), review version management")
        
        return recommendations
    
    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current metrics snapshot"""
        if not self.metrics_history:
            return {}
        
        latest_data = self.metrics_history[-1]
        return latest_data['metrics']
    
    def get_current_health(self) -> Dict[str, Any]:
        """Get current health status"""
        if not self.metrics_history:
            return {}
        
        latest_data = self.metrics_history[-1]
        return latest_data['health']
    
    def get_recent_alerts(self, count: int = 10) -> List[Alert]:
        """Get recent alerts"""
        return list(self.alert_history)[-count:]
    
    def get_metrics_trend(self, hours: int = 24) -> Dict[str, Any]:
        """Get metrics trend over specified hours"""
        if not self.metrics_history:
            return {}
        
        cutoff_time = time.time() - (hours * 3600)
        recent_data = [
            entry for entry in self.metrics_history
            if entry['timestamp'] >= cutoff_time
        ]
        
        if not recent_data:
            return {}
        
        # Calculate trends
        hit_rates = [entry['metrics'].get('overall_hit_rate', 0.0) for entry in recent_data]
        latencies = [entry['metrics'].get('avg_get_time_ms', 0.0) for entry in recent_data]
        
        return {
            'period_hours': hours,
            'data_points': len(recent_data),
            'hit_rate_trend': {
                'current': hit_rates[-1] if hit_rates else 0.0,
                'average': sum(hit_rates) / len(hit_rates) if hit_rates else 0.0,
                'min': min(hit_rates) if hit_rates else 0.0,
                'max': max(hit_rates) if hit_rates else 0.0
            },
            'latency_trend': {
                'current': latencies[-1] if latencies else 0.0,
                'average': sum(latencies) / len(latencies) if latencies else 0.0,
                'min': min(latencies) if latencies else 0.0,
                'max': max(latencies) if latencies else 0.0
            }
        }
    
    def resolve_alert(self, alert_id: str) -> bool:
        """Mark alert as resolved"""
        for alert in self.alert_history:
            if str(id(alert)) == alert_id:
                alert.resolved = True
                alert.resolution_time = time.time()
                logger.info(f"Alert resolved: {alert.message}")
                return True
        
        return False
    
    def get_monitoring_status(self) -> Dict[str, Any]:
        """Get monitoring system status"""
        return {
            'is_monitoring': self.is_monitoring,
            'config': self.config,
            'alert_thresholds': self.alert_thresholds,
            'metrics_history_size': len(self.metrics_history),
            'alerts_history_size': len(self.alert_history),
            'last_health_check': self.last_health_check,
            'last_metrics_report': self.last_metrics_report
        }


class CacheMetricsCollector:
    """
    Collects and aggregates metrics from multiple cache instances
    
    Useful for distributed cache deployments.
    """
    
    def __init__(self):
        """Initialize metrics collector"""
        self.cache_instances = {}
        self.aggregated_metrics = {}
        self.last_aggregation = time.time()
    
    def register_cache_instance(self, name: str, cache_manager):
        """Register a cache instance for monitoring"""
        self.cache_instances[name] = cache_manager
        logger.info(f"Registered cache instance: {name}")
    
    def unregister_cache_instance(self, name: str):
        """Unregister a cache instance"""
        if name in self.cache_instances:
            del self.cache_instances[name]
            logger.info(f"Unregistered cache instance: {name}")
    
    def collect_metrics(self) -> Dict[str, Any]:
        """Collect metrics from all registered instances"""
        all_metrics = {}
        
        for name, cache_manager in self.cache_instances.items():
            try:
                metrics = cache_manager.get_metrics()
                all_metrics[name] = metrics
            except Exception as e:
                logger.error(f"Failed to collect metrics from {name}: {e}")
                all_metrics[name] = {'error': str(e)}
        
        # Calculate aggregated metrics
        self.aggregated_metrics = self._aggregate_metrics(all_metrics)
        self.last_aggregation = time.time()
        
        return {
            'timestamp': self.last_aggregation,
            'instances': all_metrics,
            'aggregated': self.aggregated_metrics
        }
    
    def _aggregate_metrics(self, all_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Aggregate metrics from all instances"""
        if not all_metrics:
            return {}
        
        # Sum across instances
        total_requests = 0
        total_hits = 0
        total_misses = 0
        total_errors = 0
        total_latency_saved = 0.0
        
        hit_rates = []
        latencies = []
        
        for name, metrics in all_metrics.items():
            if 'error' in metrics:
                continue
            
            total_requests += metrics.get('total_requests', 0)
            total_hits += metrics.get('cache_hits', 0)
            total_misses += metrics.get('cache_misses', 0)
            total_errors += sum([
                metrics.get('semantic_query_metrics', {}).get('errors', 0),
                metrics.get('embedding_metrics', {}).get('errors', 0),
                metrics.get('system_prompt_metrics', {}).get('errors', 0)
            ])
            total_latency_saved += metrics.get('total_latency_saved_ms', 0.0)
            
            # Collect for averaging
            if 'overall_hit_rate' in metrics:
                hit_rates.append(metrics['overall_hit_rate'])
            if 'avg_get_time_ms' in metrics:
                latencies.append(metrics['avg_get_time_ms'])
        
        # Calculate aggregates
        overall_hit_rate = total_hits / total_requests if total_requests > 0 else 0.0
        avg_hit_rate = sum(hit_rates) / len(hit_rates) if hit_rates else 0.0
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
        
        return {
            'total_instances': len(all_metrics),
            'total_requests': total_requests,
            'total_hits': total_hits,
            'total_misses': total_misses,
            'total_errors': total_errors,
            'overall_hit_rate': overall_hit_rate,
            'avg_hit_rate_per_instance': avg_hit_rate,
            'avg_latency_per_instance': avg_latency,
            'total_latency_saved_ms': total_latency_saved,
            'aggregation_timestamp': self.last_aggregation
        }


# Convenience functions for creating monitoring components
def create_cache_monitor(cache_manager, alert_callbacks: List[Callable] = None) -> CacheMonitor:
    """
    Create and initialize cache monitor
    
    Args:
        cache_manager: Cache manager to monitor
        alert_callbacks: List of alert callback functions
        
    Returns:
        Initialized CacheMonitor instance
    """
    return CacheMonitor(cache_manager, alert_callbacks)


def create_metrics_collector() -> CacheMetricsCollector:
    """
    Create and initialize metrics collector
    
    Returns:
        Initialized CacheMetricsCollector instance
    """
    return CacheMetricsCollector()


# Alert callback examples
async def log_alert_callback(alert: Alert):
    """Example alert callback that logs alerts"""
    logger.warning(f"ALERT [{alert.severity.upper()}]: {alert.message}")


async def email_alert_callback(alert: Alert):
    """Example alert callback that sends emails (placeholder)"""
    if alert.severity in ['error', 'critical']:
        # In practice, this would send an email
        logger.info(f"Would send email alert: {alert.message}")


__all__ = [
    'CacheMonitor',
    'CacheMetricsCollector',
    'Alert',
    'MonitoringReport',
    'create_cache_monitor',
    'create_metrics_collector',
    'log_alert_callback',
    'email_alert_callback'
]