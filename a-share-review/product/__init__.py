"""Product-level orchestration and rendering."""

from .dashboard import render_dashboard
from .pipeline import run_product_day

__all__ = ["render_dashboard", "run_product_day"]
