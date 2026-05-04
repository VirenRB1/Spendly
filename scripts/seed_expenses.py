"""One-off seed script invoked by /seed-expense. Generates randomised but
realistic expense rows for a given user across the last N months.
"""
import random
import sys
from datetime import date, timedelta

from database.db import get_db


CATEGORIES = [
    ("Food",          (50,   800),  6, [
        "Lunch at canteen", "Groceries from kirana", "Chai and snacks",
        "Dinner with friends", "Biryani takeaway", "Vegetables from market",
        "Sweets from local shop", "Office cafeteria meal",
    ]),
    ("Transport",     (20,   500),  4, [
        "Auto rickshaw", "Metro card recharge", "Petrol fill-up",
        "Ola ride", "Uber to office", "Bus pass", "Parking fee",
    ]),
    ("Bills",         (200, 3000),  3, [
        "Electricity bill", "Mobile recharge", "Internet bill",
        "Gas cylinder", "Water bill", "DTH recharge",
    ]),
    ("Shopping",      (200, 5000),  3, [
        "Clothes from Myntra", "Footwear", "Electronics accessory",
        "Home decor", "Books from Flipkart", "Kitchenware",
    ]),
    ("Other",         (50,  1000),  2, [
        "Stationery", "Gift for friend", "Donation",
        "Repair work", "Miscellaneous",
    ]),
    ("Entertainment", (100, 1500),  1, [
        "OTT subscription", "Movie tickets", "Concert tickets",
        "Bowling night", "Game purchase",
    ]),
    ("Health",        (100, 2000),  1, [
        "Pharmacy", "Doctor consultation", "Lab tests",
        "Gym membership", "Vitamins",
    ]),
]


def pick_category():
    population = []
    for cat, _, weight, _ in CATEGORIES:
        population.extend([cat] * weight)
    return random.choice(population)


def category_meta(name):
    for cat, bounds, _, descs in CATEGORIES:
        if cat == name:
            return bounds, descs
    raise ValueError(name)


def main(user_id, count, months):
    conn = get_db()
    user = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        conn.close()
        print(f"No user found with id {user_id}.")
        sys.exit(1)

    today = date.today()
    earliest = today - timedelta(days=months * 30)
    span_days = (today - earliest).days

    rows = []
    for _ in range(count):
        cat = pick_category()
        (lo, hi), descs = category_meta(cat)
        amount = round(random.uniform(lo, hi), 2)
        d = earliest + timedelta(days=random.randint(0, span_days))
        rows.append((user_id, amount, cat, d.isoformat(), random.choice(descs)))

    try:
        conn.execute("BEGIN")
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        conn.close()
        raise

    sample = conn.execute(
        "SELECT date, category, amount, description FROM expenses "
        "WHERE user_id = ? ORDER BY id DESC LIMIT ?",
        (user_id, min(5, count)),
    ).fetchall()
    conn.close()

    dates = [r[3] for r in rows]
    print(f"Inserted {len(rows)} expenses for user {user_id}.")
    print(f"Date range: {min(dates)} to {max(dates)}")
    print("Sample (5 most recent inserts):")
    for s in sample:
        print(f"  {s['date']}  {s['category']:<14} ₹{s['amount']:>8.2f}  {s['description']}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python scripts/seed_expenses.py <user_id> <count> <months>")
        sys.exit(1)
    try:
        uid, cnt, mon = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
    except ValueError:
        print("Usage: /seed-expenses <user_id> <count> <months>\nExample: /seed-expenses 1 50 6")
        sys.exit(1)
    main(uid, cnt, mon)
