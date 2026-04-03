"""
MLM Commission Configuration
RK Trendz Plan (Enterprise Decimal Precision)
"""
from decimal import Decimal

# We wrap the numbers in quotes inside Decimal() to prevent 
# Python from reading them as flawed 'floats' first.
COMMISSION_LEVELS = {
    1: Decimal('0.03'),    # 3%
    2: Decimal('0.025'),   # 2.5%
    3: Decimal('0.015'),   # 1.5%
    4: Decimal('0.01'),    # 1%
    5: Decimal('0.01'),    # 1%
    6: Decimal('0.01'),    # 1%
    7: Decimal('0.01'),    # 1%
    8: Decimal('0.0075'),  # 0.75%
    9: Decimal('0.006'),   # 0.60%
    10: Decimal('0.005')   # 0.50%
}
