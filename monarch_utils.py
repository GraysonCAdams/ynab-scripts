import os
from dotenv import load_dotenv
from cachetools import TTLCache
from monarchmoney import MonarchMoney, RequireMFAException
from datetime import datetime, timedelta

load_dotenv()

EMAIL = os.environ.get("MONARCH_MONEY_EMAIL")
PASSWORD = os.environ.get("MONARCH_MONEY_PASSWORD")
MFA_SECRET_KEY = os.environ.get("MFA_SECRET_KEY")


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
async def get_mm():
    mm = MonarchMoney()
    session_file = getattr(mm, "_session_file", None)
    use_saved_session = False
    if session_file and os.path.exists(session_file):
        mtime = datetime.fromtimestamp(os.path.getmtime(session_file))
        if (datetime.now() - mtime).total_seconds() < 300:
            print(f"Using saved session from {session_file}.")
            use_saved_session = True
        else:
            print(f"Session file {session_file} is too old, removing.")
            os.remove(session_file)
    await mm.login(
        email=EMAIL,
        password=PASSWORD,
        mfa_secret_key=MFA_SECRET_KEY,
        use_saved_session=use_saved_session,
    )
    return mm


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
