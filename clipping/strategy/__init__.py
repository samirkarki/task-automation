"""
Strategy optimization package for continuous algorithmic improvement:
- A/B testing evaluation
- Automated parameter & prompt optimizer
- Weekly performance report generator
"""

from clipping.strategy.ab_tester import evaluate_ab_test
from clipping.strategy.optimizer import StrategyOptimizer
from clipping.strategy.weekly_report import generate_weekly_report

__all__ = ["evaluate_ab_test", "StrategyOptimizer", "generate_weekly_report"]
