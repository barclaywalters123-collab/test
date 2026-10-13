"""Business settings the agent uses for its money math. Change these to match your situation."""

# eBay selling fees: roughly 13.6% of the sale + $0.40 per order in most categories.
# Check eBay's current fee page for your category.
FEE_RATE = 0.136
FEE_PER_ORDER = 0.40

# Profit you want to keep, as a share of the sale price (0.30 = 30%).
TARGET_MARGIN = 0.30

# The most you want to pay per unit from your bulk supplier.
MAX_UNIT_BUDGET = 25.00
