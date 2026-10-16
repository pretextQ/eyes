"""Candidate materials explicitly authorized for offline scorer verification, 2026-10-16."""

CHUNKS = """def chunk(items, size):
    if not isinstance(items, list):
        raise TypeError
    if type(size) is not int:
        raise TypeError
    if size <= 0:
        raise ValueError
    return [items[i:i + size] for i in range(0, len(items), size)]
"""

INTSUM = """import json
import re
import sys

def main():
    if any(re.fullmatch(r"[+-]?[0-9]+", value) is None for value in sys.argv[1:]):
        print("invalid integer", file=sys.stderr)
        return 2
    print(json.dumps({"count": len(sys.argv) - 1, "sum": sum(map(int, sys.argv[1:]))}))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
"""

MONEY = """def discounted_cents(price_cents, discount_bps):
    if type(price_cents) is not int or price_cents < 0:
        raise ValueError
    if type(discount_bps) is not int or not 0 <= discount_bps <= 10000:
        raise ValueError
    return (price_cents * (10000 - discount_bps) + 5000) // 10000
"""

ORDER = """from money import discounted_cents

def total_cents(items, discount_bps=0):
    discounted_cents(0, discount_bps)
    if not isinstance(items, list):
        raise ValueError
    result = 0
    for row in items:
        if not isinstance(row, dict) or set(row) != {"price_cents", "quantity"}:
            raise ValueError
        quantity = row["quantity"]
        if type(quantity) is not int or quantity < 0:
            raise ValueError
        result += discounted_cents(row["price_cents"], discount_bps) * quantity
    return result
"""

MAIN = """import json
import sys
from order import total_cents

def pairs(values):
    result = {}
    for key, value in values:
        if key in result:
            raise ValueError
        result[key] = value
    return result

def constant(value):
    raise ValueError

def main():
    try:
        if len(sys.argv) != 2:
            raise ValueError
        with open(sys.argv[1], encoding="utf-8") as stream:
            value = json.load(stream, object_pairs_hook=pairs, parse_constant=constant)
        if not isinstance(value, dict) or set(value) != {"items", "discount_bps"}:
            raise ValueError
        total = total_cents(value["items"], value["discount_bps"])
    except (ValueError, TypeError, OSError, UnicodeError):
        print("invalid order", file=sys.stderr)
        return 2
    print(json.dumps({"total_cents": total}))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
"""

CORRECT = {
    "py-chunk-sequence": {"chunks.py": CHUNKS},
    "py-int-cli-errors": {"intsum.py": INTSUM},
    "py-order-pricing-project": {"money.py": MONEY, "order.py": ORDER, "main.py": MAIN},
}
