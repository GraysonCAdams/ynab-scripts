from datetime import datetime, timedelta
import asyncio
from flask import Flask, request, jsonify
from functools import wraps
import inspect
from monarch_utils import (
    get_mm,
    build_category_maps,
    get_month_range,
)
import pprint
import math

app = Flask(__name__)


# Helper to allow async Flask views (Python 3.8+)
def async_flask(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if inspect.iscoroutinefunction(f):
            return asyncio.run(f(*args, **kwargs))
        return f(*args, **kwargs)

    return wrapper


async def get_category_balance(category_name, group=False):
    mm = await get_mm()
    start, _ = get_month_range()
    budgets = await mm.get_budgets(start, start)
    month_key = start
    cat_id_to_name, cat_name_to_id, monthly_lookup = build_category_maps(budgets)

    def get_maps():
        if group:
            return (
                cat_id_to_name["categoryGroups"],
                cat_name_to_id["categoryGroups"],
                monthly_lookup["categoryGroups"],
            )
        else:
            return (
                cat_id_to_name["categories"],
                cat_name_to_id["categories"],
                monthly_lookup["categories"],
            )

    def _get_balance(category_name):
        id_to_name, name_to_id, month_lookup = get_maps()
        cat_id = name_to_id.get(category_name.lower())
        if cat_id:
            m = month_lookup.get((cat_id, month_key))
            if m:
                return {
                    "category": id_to_name[cat_id],
                    "plannedCashFlowAmount": m.get("plannedCashFlowAmount"),
                    "plannedSetAsideAmount": m.get("plannedSetAsideAmount"),
                    "actualAmount": m.get("actualAmount"),
                    "remainingAmount": m.get("remainingAmount"),
                }
        return {"error": f"Category '{category_name}' not found."}, 404

    # Default to group=False for backward compatibility
    return _get_balance(category_name)


async def set_category_balance(category_name, amount, group=False):
    mm = await get_mm()
    today = get_month_range()[1]
    budgets = await mm.get_budgets(today, today)
    _, cat_name_to_id, _ = build_category_maps(budgets)
    name_to_id = (
        cat_name_to_id["categoryGroups"] if group else cat_name_to_id["categories"]
    )
    cat_id = name_to_id.get(category_name.lower())
    if not cat_id:
        return {"error": f"Category '{category_name}' not found."}, 404
    pprint.pprint(
        amount,
        category_id=cat_id if not group else None,
        category_group_id=cat_id if group else None,
        timeframe="month",
        start_date=today,
        apply_to_future=False,
    )
    await mm.set_budget_amount(
        amount,
        category_id=cat_id if not group else None,
        category_group_id=cat_id if group else None,
        timeframe="month",
        start_date=today,
        apply_to_future=False,
    )
    return {"message": f"Budget for '{category_name}' set to {amount}"}


async def get_flex_amount():
    mm = await get_mm()
    start, end = get_month_range()
    budgets = await mm.get_budgets(start, end)
    flex = budgets["budgetData"]["totalsByMonth"][0]["totalFlexibleExpenses"][
        "plannedAmount"
    ]
    return {"flexible_budget": flex}


async def set_flex_amount(amount):
    mm = await get_mm()

    today = get_month_range()[1]
    await mm.update_flexible_budget(amount, today, False)
    return {"message": f"Flexible budget set to {amount}"}


@app.route("/category", methods=["POST"])
@async_flask
def category_get():
    data = request.get_json()
    category_name = data.get("category_name")
    if not category_name:
        return jsonify({"error": "Missing 'category_name' in request body."}), 400
    return jsonify(asyncio.run(get_category_balance(category_name)))


@app.route("/category/set", methods=["POST"])
@async_flask
def category_set():
    data = request.get_json()
    category_name = data.get("category_name")
    amount = data.get("amount")
    if not category_name or amount is None:
        return (
            jsonify({"error": "Missing 'category_name' or 'amount' in request body."}),
            400,
        )
    return jsonify(asyncio.run(set_category_balance(category_name, amount)))


@app.route("/category-group/<category_name>", methods=["GET"])
@async_flask
def category_group_get(category_name):
    return jsonify(asyncio.run(get_category_balance(category_name, group=True)))


@app.route("/category-group/<category_name>", methods=["POST"])
@async_flask
def category_group_set(category_name):
    data = request.get_json()
    amount = data.get("amount")
    if amount is None:
        return jsonify({"error": "Missing 'amount' in request body."}), 400
    return jsonify(asyncio.run(set_category_balance(category_name, amount, group=True)))


@app.route("/flex", methods=["GET"])
@async_flask
def flex_get():
    return jsonify(asyncio.run(get_flex_amount()))


@app.route("/flex", methods=["POST"])
@async_flask
def flex_set():
    data = request.get_json()
    amount = data.get("amount")
    if amount is None:
        return jsonify({"error": "Missing 'amount' in request body."}), 400
    return jsonify(asyncio.run(set_flex_amount(amount)))


async def get_recurring_transactions():
    mm = await get_mm()
    # Only quarterly, semiyearly, yearly frequencies, include liabilities
    return await mm.get_all_recurring_transaction_items(
        frequencies=["quarterly", "semiyearly", "yearly"],
        include_liabilities=True,
    )


async def update_periodic_transactions_budget():
    mm = await get_mm()
    recurring = await mm.get_all_recurring_transaction_items(
        frequencies=["quarterly", "semiyearly", "yearly"],
        include_liabilities=True,
    )
    items = recurring.get("recurringTransactionStreams", [])

    # Build a mapping: {month: total_amount} for non-monthly frequencies only
    from collections import defaultdict

    month_totals = defaultdict(float)
    today = datetime.now().date()
    for item in items:
        next_txn = item.get("nextForecastedTransaction", {})
        date_str = next_txn.get("date")
        amount = next_txn.get("amount", 0)
        if not date_str or not amount:
            continue
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        if date_obj >= today:
            month_key = date_obj.strftime("%Y-%m")
            month_totals[month_key] += amount

    # Get budgets and category id for 'Periodic Subscriptions'
    budgets = await mm.get_budgets(
        today.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")
    )
    _, cat_name_to_id, _ = build_category_maps(budgets)
    periodic_id = cat_name_to_id["categories"].get("periodic subscriptions")
    if not periodic_id:
        return {"error": "Category 'Periodic Subscriptions' not found."}, 404

    results = []
    for month_key, total in month_totals.items():
        # Use first day of month for start_date
        year, month = map(int, month_key.split("-"))
        first_day = datetime(year, month, 1).strftime("%Y-%m-%d")
        rounded_total = math.ceil(abs(total))
        await mm.set_budget_amount(
            rounded_total,
            category_id=periodic_id,
            category_group_id=None,
            timeframe="month",
            start_date=first_day,
            apply_to_future=False,
        )
        results.append({"month": month_key, "amount": rounded_total})
    return {"updated": results}


@app.route("/periodic/update", methods=["GET"])
@async_flask
def periodic_update():
    return jsonify(asyncio.run(update_periodic_transactions_budget()))


def create_app():
    return app


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
