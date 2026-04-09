"""Compatibility facade for admin query APIs.

This module keeps stable imports for routers/workers while delegating to
focused query modules for cleaner structure.
"""

from database.queries.dashboard import (
    fetch_dashboard_activity,
    fetch_dashboard_analytics,
    fetch_dashboard_data,
)
from database.queries.reporting import fetch_daily_summary
from database.queries.tickets import fetch_assigned_tickets

__all__ = [
    "fetch_dashboard_data",
    "fetch_dashboard_analytics",
    "fetch_dashboard_activity",
    "fetch_daily_summary",
    "fetch_assigned_tickets",
]
