"""Write the small billing project the Claude Code cost benchmark runs on.

Task "one-bug" has a single bug (refund rounding). Task "three-bugs" adds two more (an exclusive date range and a
missing same-currency case). About 260 parametrized tests pass either way, so `pytest -v` prints roughly 22 KB: long
enough to matter, short enough that Claude Code passes it to the model whole instead of saving it to a file.

Usage: python make_fixture.py {one-bug,three-bugs} DEST
"""

import sys
from pathlib import Path

MONEY = '''from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def round_money(amount: Decimal) -> Decimal:
    """Round to whole cents with banker's rounding (half to even), as the ledger requires."""
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)
'''

REFUND = '''from decimal import Decimal

from billing.money import round_money


def prorated_refund(total: Decimal, days_used: int, days_total: int) -> Decimal:
    """What to refund when a customer cancels after days_used of a days_total period."""
    if not 0 <= days_used <= days_total:
        raise ValueError("days_used must be between 0 and days_total")
    return round_money(total * (days_total - days_used) / days_total)
'''

INVOICE = '''def line_total(quantity: int, unit_cents: int) -> int:
    """Total for one invoice line, in cents."""
    if quantity < 0 or unit_cents < 0:
        raise ValueError("quantity and price must not be negative")
    return quantity * unit_cents


def invoice_total(lines: list[tuple[int, int]]) -> int:
    return sum(line_total(quantity, unit) for quantity, unit in lines)
'''

TAX = '''def tax_cents(amount_cents: int, rate_bp: int) -> int:
    """Tax on an amount in cents at a rate in basis points (825 = 8.25%), rounded half up."""
    return (amount_cents * rate_bp + 5_000) // 10_000
'''

PERIODS_BUGGY = '''from datetime import date


def days_in_period(start: date, end: date) -> int:
    """Number of billable days from start to end, counting both days."""
    if end < start:
        raise ValueError("end is before start")
    return (end - start).days
'''

PERIODS_OK = PERIODS_BUGGY.replace("return (end - start).days", "return (end - start).days + 1")

CURRENCY_BUGGY = '''RATES_PPM = {("USD", "EUR"): 920_000, ("EUR", "USD"): 1_087_000, ("USD", "INR"): 83_100_000}


def convert(cents: int, source: str, target: str) -> int:
    """Convert an amount in cents between currencies, using rates in parts per million."""
    rate = RATES_PPM[(source, target)]
    return cents * rate // 1_000_000
'''

CURRENCY_OK = CURRENCY_BUGGY.replace(
    "    rate = RATES_PPM[(source, target)]",
    "    if source == target:\n        return cents\n    rate = RATES_PPM[(source, target)]",
)

TEST_REFUND = """from decimal import Decimal

import pytest

from billing.refund import prorated_refund


def test_full_refund_before_use():
    assert prorated_refund(Decimal("30.00"), 0, 30) == Decimal("30.00")


def test_half_cent_rounds_to_even():
    # 20.09 / 2 = 10.045, and the ledger rounds half to even
    assert prorated_refund(Decimal("20.09"), 1, 2) == Decimal("10.04")


def test_days_out_of_range():
    with pytest.raises(ValueError):
        prorated_refund(Decimal("10.00"), 5, 4)
"""

TEST_INVOICE = """import pytest

from billing.invoice import invoice_total, line_total


@pytest.mark.parametrize("case", range(100))
def test_line_total(case):
    quantity, unit = case % 7 + 1, 199 + case * 3
    assert line_total(quantity, unit) == quantity * unit


def test_invoice_total():
    assert invoice_total([(2, 500), (1, 250)]) == 1250
"""

TEST_TAX = """import pytest

from billing.tax import tax_cents


@pytest.mark.parametrize("case", range(80))
def test_whole_cent_tax(case):
    amount, rate = 100 * (case + 1), 100 * (case % 12 + 1)
    assert tax_cents(amount, rate) == amount * rate // 10_000


def test_rounds_half_up():
    assert tax_cents(1_000, 825) == 83
"""

TEST_CURRENCY = """import pytest

from billing.currency import convert


@pytest.mark.parametrize("case", range(75))
def test_usd_to_eur(case):
    cents = 1_000 * (case + 1)
    assert convert(cents, "USD", "EUR") == cents * 92 // 100


def test_same_currency_is_unchanged():
    assert convert(500, "EUR", "EUR") == 500
"""

TEST_PERIODS = """from datetime import date

from billing.periods import days_in_period


def test_one_day_period():
    assert days_in_period(date(2026, 3, 1), date(2026, 3, 1)) == 1


def test_whole_month():
    assert days_in_period(date(2026, 3, 1), date(2026, 3, 31)) == 31
"""


def write(dest: Path, task: str) -> None:
    three = task == "three-bugs"
    files = {
        "pytest.ini": "[pytest]\npythonpath = .\ntestpaths = tests\n",
        "billing/__init__.py": "",
        "billing/money.py": MONEY,
        "billing/refund.py": REFUND,
        "billing/invoice.py": INVOICE,
        "billing/tax.py": TAX,
        "billing/periods.py": PERIODS_BUGGY if three else PERIODS_OK,
        "billing/currency.py": CURRENCY_BUGGY if three else CURRENCY_OK,
        "tests/test_refund.py": TEST_REFUND,
        "tests/test_invoice.py": TEST_INVOICE,
        "tests/test_tax.py": TEST_TAX,
        "tests/test_currency.py": TEST_CURRENCY,
        "tests/test_periods.py": TEST_PERIODS,
    }
    for name, text in files.items():
        path = dest / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("one-bug", "three-bugs"):
        raise SystemExit(__doc__)
    write(Path(sys.argv[2]), sys.argv[1])
