import pytest
from decimal import Decimal

# Import your actual configuration from your codebase
from app.config.commission_levels import COMMISSION_LEVELS

def test_commission_levels_loaded():
    """Ensure the system successfully loads the commission levels."""
    assert isinstance(COMMISSION_LEVELS, dict), "Commission levels should be a dictionary."
    assert len(COMMISSION_LEVELS) > 0, "Commission levels cannot be empty!"

def test_maximum_payout_safety():
    """
    CRITICAL: Ensure the total percentage paid out across all levels 
    does not exceed 100%. If it does, the company will lose money on every sale.
    """
    total_payout_percentage = sum(COMMISSION_LEVELS.values())
    
    # We allow up to 100% (though usually MLMs cap at 40-60%)
    assert total_payout_percentage <= 100, f"FATAL ERROR: Total payout is {total_payout_percentage}%, which exceeds 100%!"

def test_level_progression_logic():
    """Ensure that higher levels (further down the tree) generally pay less or equal to level 1."""
    level_1_payout = COMMISSION_LEVELS.get(1, 0)
    level_5_payout = COMMISSION_LEVELS.get(5, 0)
    
    if level_5_payout > 0:
        assert level_1_payout >= level_5_payout, "Warning: Level 5 pays more than Level 1. This is unusual for MLM structures."
