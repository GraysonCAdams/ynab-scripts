import asyncio
from flask import Flask, request, jsonify
from functools import wraps
import inspect
from monarch_utils import (
    login_and_get_mm,
    build_category_maps,
    get_month_range,
)

app = Flask(__name__)


# Helper to allow async Flask views (Python 3.8+)
def async_flask(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if inspect.iscoroutinefunction(f):
            return asyncio.run(f(*args, **kwargs))
        return f(*args, **kwargs)

    return wrapper


async def get_category_balance(category_name):
    mm, error = await login_and_get_mm()
    if error:
        return error
    start, _ = get_month_range()
    budgets = await mm.get_budgets(start, start)
    month_key = start
    cat_id_to_name, cat_name_to_id, monthly_lookup = build_category_maps(budgets)
    cat_id = cat_name_to_id.get(category_name.lower())
    if cat_id:
        m = monthly_lookup.get((cat_id, month_key))
        if m:
            return {
                "category": cat_id_to_name[cat_id],
                "plannedCashFlowAmount": m.get("plannedCashFlowAmount"),
                "plannedSetAsideAmount": m.get("plannedSetAsideAmount"),
                "actualAmount": m.get("actualAmount"),
                "remainingAmount": m.get("remainingAmount"),
            }
    return {"error": f"Category '{category_name}' not found."}, 404


async def set_category_balance(category_name, amount):
    mm, error = await login_and_get_mm()
    if error:
        return error
    today = get_month_range()[1]
    budgets = await mm.get_budgets(today, today)
    _, cat_name_to_id, _ = build_category_maps(budgets)
    cat_id = cat_name_to_id.get(category_name.lower())
    if not cat_id:
        return {"error": f"Category '{category_name}' not found."}, 404
    # Use correct argument order for set_budget_amount
    await mm.set_budget_amount(
        amount,
        category_id=cat_id,
        timeframe="month",
        start_date=today,
        apply_to_future=False,
    )
    return {"message": f"Budget for '{category_name}' set to {amount}"}


async def get_flex_amount():
    mm, error = await login_and_get_mm()
    if error:
        return error
    start, end = get_month_range()
    budgets = await mm.get_budgets(start, end)
    flex = budgets["budgetData"]["totalsByMonth"][0]["totalFlexibleExpenses"][
        "plannedAmount"
    ]
    return {"flexible_budget": flex}


async def set_flex_amount(amount):
    mm, error = await login_and_get_mm()
    if error:
        return error
    today = get_month_range()[1]
    await mm.update_flexible_budget(amount, today, False)
    return {"message": f"Flexible budget set to {amount}"}


@app.route("/category/<category_name>", methods=["GET"])
@async_flask
def category_get(category_name):
    return jsonify(asyncio.run(get_category_balance(category_name)))


@app.route("/category/<category_name>", methods=["POST"])
@async_flask
def category_set(category_name):
    data = request.get_json()
    amount = data.get("amount")
    if amount is None:
        return jsonify({"error": "Missing 'amount' in request body."}), 400
    return jsonify(asyncio.run(set_category_balance(category_name, amount)))


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


def create_app():
    return app


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
