import os
from dotenv import load_dotenv
from cachetools import TTLCache
from monarchmoney import MonarchMoney, RequireMFAException
from datetime import datetime, timedelta

load_dotenv()

EMAIL = os.environ.get("MONARCH_MONEY_EMAIL")
PASSWORD = os.environ.get("MONARCH_MONEY_PASSWORD")
MFA_SECRET_KEY = os.environ.get("MFA_SECRET_KEY")

mm_cache = TTLCache(maxsize=1, ttl=300)


def get_mm():
    if "mm" in mm_cache:
        return mm_cache["mm"]
    mm = MonarchMoney()
    mm_cache["mm"] = mm
    return mm


def get_month_range():
    now = datetime.now()
    start = now.replace(day=1).strftime("%Y-%m-%d")
    if now.month == 12:
        end = now.replace(year=now.year + 1, month=1, day=1)
    else:
        end = now.replace(month=now.month + 1, day=1)
    end = (end - timedelta(days=1)).strftime("%Y-%m-%d")
    return start, end


# Helper to login and handle MFA exception, returns (mm, error_response or None)
async def login_and_get_mm():
    mm = get_mm()
    try:
        await mm.login(email=EMAIL, password=PASSWORD, mfa_secret_key=MFA_SECRET_KEY)
        mm._is_logged_in = True
        return mm, None
    except RequireMFAException:
        mm._is_logged_in = False
        return (
            None,
            {"error": "MFA required. Set up MFA_SECRET_KEY in environment."},
            401,
        )


# Helper to build category id<->name maps and monthly lookup
def build_category_maps(budgets):
    cat_id_to_name = {
        cat["id"]: cat["name"]
        for group in budgets.get("categoryGroups", [])
        for cat in group.get("categories", [])
    }
    cat_name_to_id = {v.lower(): k for k, v in cat_id_to_name.items()}
    monthly = budgets["budgetData"].get("monthlyAmountsByCategory", [])
    monthly_lookup = {
        (entry["category"]["id"], m["month"]): m
        for entry in monthly
        for m in entry["monthlyAmounts"]
    }
    print(cat_id_to_name)
    return cat_id_to_name, cat_name_to_id, monthly_lookup
