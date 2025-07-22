# monarch.py
# Script to add $15 to the "Flexible" budget in Monarch Money using the monarchmoney API
# Usage: Fill in your Monarch Money credentials below

import asyncio
import os
from monarchmoney import MonarchMoney, RequireMFAException

EMAIL = os.environ.get("MONARCH_MONEY_EMAIL")  # <-- Replace with your Monarch Money email
PASSWORD = os.environ.get("MONARCH_MONEY_PASSWORD")       # <-- Replace with your Monarch Money password
MFA_SECRET_KEY = os.environ.get("MFA_SECRET_KEY")             # <-- Optional: Replace with your MFA secret key if needed

CATEGORY_NAME = "Flexible"
AMOUNT = 15.0

async def main():
    mm = MonarchMoney()
    try:
        # Login (add MFA_SECRET_KEY if needed)
        await mm.login(email=EMAIL, password=PASSWORD, mfa_secret_key=MFA_SECRET_KEY)
    except RequireMFAException:
        mfa_code = input("Enter MFA code: ")
        await mm.multi_factor_authenticate(EMAIL, PASSWORD, mfa_code)

    budgets = await mm.get_budgets("2025-07-01", "2025-07-31")
    flex = budgets["budgetData"]["totalsByMonth"][0]["totalFlexibleExpenses"]["plannedAmount"]
    print(flex)
    # await mm.update_flexible_budget(1000.00, "2025-07-22", False)

if __name__ == "__main__":
    asyncio.run(main())
