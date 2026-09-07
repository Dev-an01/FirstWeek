"""
LLM Cost Tracker
================

Tracks LLM token usage and costs in real-time.

Features:
- Token counting per model
- Cost calculation based on pricing
- Daily/monthly aggregation
- Cost alerts
- Per-executive cost tracking

Usage:
    from observability.cost_tracker import CostTracker
    
    cost = CostTracker.track_llm_usage(
        model="gpt-4o",
        prompt_tokens=450,
        completion_tokens=320,
        path="standard",
        executive_id="exec_001"
    )
"""

from typing import Dict, Optional
from datetime import datetime, timedelta
import threading

from .logging import StructuredLogger
from .metrics import (
    llm_tokens_counter,
    llm_cost_counter,
)
from .config import DEFAULT_LLM_PRICING, COST_TRACKING_ENABLED

logger = StructuredLogger(__name__)


class CostTracker:
    """
    Track LLM token usage and costs.
    
    Provides real-time cost tracking with alerts and aggregation.
    """
    
    # In-memory cost tracking (for daily aggregation)
    _daily_costs: Dict[str, float] = {}
    _cost_lock = threading.Lock()
    _last_reset = datetime.utcnow().date()
    
    @staticmethod
    def track_llm_usage(
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        path: str,
        executive_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> float:
        """
        Track LLM usage and return cost.
        
        Args:
            model: Model name
            prompt_tokens: Input tokens used
            completion_tokens: Output tokens used
            path: Query path (fast/standard/agentic)
            executive_id: Optional executive profile ID
            user_id: Optional user ID
            
        Returns:
            Cost in USD
            
        Example:
            cost = CostTracker.track_llm_usage(
                model="gpt-4o",
                prompt_tokens=450,
                completion_tokens=320,
                path="standard",
                executive_id="exec_001"
            )
        """
        if not COST_TRACKING_ENABLED:
            return 0.0
        
        # Get pricing for model
        pricing = DEFAULT_LLM_PRICING.get(model, {
            'input': 0.000005,  # Default to GPT-4o pricing
            'output': 0.000015
        })
        
        # Calculate cost (pricing is per 1K tokens, but stored as per token)
        input_cost = (prompt_tokens / 1000) * pricing['input']
        output_cost = (completion_tokens / 1000) * pricing['output']
        total_cost = input_cost + output_cost
        
        # Update metrics
        llm_tokens_counter.labels(model=model, token_type='prompt').inc(prompt_tokens)
        llm_tokens_counter.labels(model=model, token_type='completion').inc(completion_tokens)
        llm_cost_counter.labels(model=model, path=path).inc(total_cost)
        
        # Update daily cost tracking
        CostTracker._update_daily_cost(model, total_cost)
        
        # Log cost
        logger.info(
            "LLM usage tracked",
            model=model,
            path=path,
            executive_id=executive_id,
            user_id=user_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            input_cost_usd=round(input_cost, 6),
            output_cost_usd=round(output_cost, 6),
            total_cost_usd=round(total_cost, 6)
        )
        
        return total_cost
    
    @staticmethod
    def _update_daily_cost(model: str, cost: float) -> None:
        """Update daily cost tracking"""
        with CostTracker._cost_lock:
            # Check if need to reset daily costs
            today = datetime.utcnow().date()
            if today != CostTracker._last_reset:
                logger.info(
                    "Daily cost reset",
                    previous_date=str(CostTracker._last_reset),
                    total_cost=sum(CostTracker._daily_costs.values())
                )
                CostTracker._daily_costs = {}
                CostTracker._last_reset = today
            
            # Add to daily cost
            if model not in CostTracker._daily_costs:
                CostTracker._daily_costs[model] = 0.0
            CostTracker._daily_costs[model] += cost
    
    @staticmethod
    def get_daily_cost(model: Optional[str] = None) -> float:
        """
        Get daily cost.
        
        Args:
            model: Optional model name to filter by
            
        Returns:
            Total daily cost in USD
        """
        with CostTracker._cost_lock:
            if model:
                return CostTracker._daily_costs.get(model, 0.0)
            return sum(CostTracker._daily_costs.values())
    
    @staticmethod
    def get_daily_cost_breakdown() -> Dict[str, float]:
        """
        Get daily cost breakdown by model.
        
        Returns:
            Dictionary mapping model name to cost
        """
        with CostTracker._cost_lock:
            return CostTracker._daily_costs.copy()
    
    @staticmethod
    def estimate_query_cost(
        model: str,
        estimated_prompt_tokens: int,
        estimated_completion_tokens: int
    ) -> float:
        """
        Estimate cost for a query before execution.
        
        Args:
            model: Model name
            estimated_prompt_tokens: Estimated input tokens
            estimated_completion_tokens: Estimated output tokens
            
        Returns:
            Estimated cost in USD
        """
        pricing = DEFAULT_LLM_PRICING.get(model, {
            'input': 0.000005,
            'output': 0.000015
        })
        
        input_cost = (estimated_prompt_tokens / 1000) * pricing['input']
        output_cost = (estimated_completion_tokens / 1000) * pricing['output']
        
        return input_cost + output_cost
    
    @staticmethod
    def get_model_pricing(model: str) -> Dict[str, float]:
        """
        Get pricing for a model.
        
        Args:
            model: Model name
            
        Returns:
            Dictionary with 'input' and 'output' pricing per 1K tokens
        """
        return DEFAULT_LLM_PRICING.get(model, {
            'input': 0.000005,
            'output': 0.000015
        })


class CostAlert:
    """
    Alert when costs exceed thresholds.
    """
    
    _last_alert_time: Optional[datetime] = None
    _alert_cooldown = timedelta(hours=1)  # Don't spam alerts
    
    @staticmethod
    def check_daily_cost_threshold(threshold: float) -> bool:
        """
        Check if daily cost exceeds threshold.
        
        Args:
            threshold: Cost threshold in USD
            
        Returns:
            True if threshold exceeded and alert should be sent
        """
        daily_cost = CostTracker.get_daily_cost()
        
        if daily_cost > threshold:
            # Check cooldown
            now = datetime.utcnow()
            if (CostAlert._last_alert_time is None or 
                now - CostAlert._last_alert_time > CostAlert._alert_cooldown):
                
                logger.warning(
                    "Daily cost threshold exceeded",
                    daily_cost_usd=daily_cost,
                    threshold_usd=threshold,
                    cost_breakdown=CostTracker.get_daily_cost_breakdown()
                )
                
                CostAlert._last_alert_time = now
                return True
        
        return False
