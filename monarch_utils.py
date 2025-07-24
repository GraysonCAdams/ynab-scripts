import json
# Helper to strip leading emoji and space from a string
import re
def _strip_emoji_and_space(name):
    return re.sub(r"^([\U0001F300-\U0001FAFF\U00002700-\U000027BF\U0001F900-\U0001F9FF\U0001F600-\U0001F64F\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\u2600-\u26FF\u2700-\u27BF]|[\u200d\u2640-\u2642\u2695-\u2696\u2708-\u2709\u231a-\u231b\u23e9-\u23ef\u23f0-\u23f3\u25fd-\u25fe\u2614-\u2615\u2744-\u2747\u2753-\u2755\u2795-\u2797\u27b0\u27bf\u2b05-\u2b07\u2934-\u2935\u2b1b-\u2b1c\u2b50\u2b55\u3030\u303d\u3297\u3299])+\s*", "", name)
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
    cat_id_to_name_categories = {}
    cat_id_to_name_groups = {}
    cat_name_to_id_categories = {}
    cat_name_to_id_groups = {}

    for group in budgets.get("categoryGroups", []):
        group_id = group["id"]
        group_name = _strip_emoji_and_space(group["name"])
        cat_id_to_name_groups[group_id] = group_name
        cat_name_to_id_groups[group_name.lower()] = group_id
        for cat in group.get("categories", []):
            cat_id = cat["id"]
            cat_name = cat["name"]
            cat_id_to_name_categories[cat_id] = cat_name
            cat_name_to_id_categories[cat_name.lower()] = cat_id

    monthly_categories = budgets["budgetData"].get("monthlyAmountsByCategory", [])
    monthly_categories_lookup = {
        (entry["category"]["id"], m["month"]): m
        for entry in monthly_categories
        for m in entry["monthlyAmounts"]
    }
    monthly_category_groups = budgets["budgetData"].get("monthlyAmountsByCategoryGroup", [])
    monthly_category_groups_lookup = {
        (entry["categoryGroup"]["id"], m["month"]): m
        for entry in monthly_category_groups
        for m in entry["monthlyAmounts"]
    }

    return {
        "categories": cat_id_to_name_categories,
        "categoryGroups": cat_id_to_name_groups
    }, {
        "categories": cat_name_to_id_categories,
        "categoryGroups": cat_name_to_id_groups
    }, {
        "categories": monthly_categories_lookup,
        "categoryGroups": monthly_category_groups_lookup
    }
