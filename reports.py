"""Turns data into printable text. Pure functions: data in, string out."""

CURRENCY = "$"  # change to your currency symbol
BAR_WIDTH = 20


def money(amount: float) -> str:
    return f"{CURRENCY}{amount:,.2f}"


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 3] + "..."


def format_table(expenses) -> str:
    if not expenses:
        return "No expenses found."

    headers = ("ID", "Date", "Category", "Description", "Amount")
    rows = [
        (str(e.id), e.date, e.category, _truncate(e.description, 30), money(e.amount))
        for e in expenses
    ]
    widths = [max(len(headers[i]), *(len(r[i]) for r in rows)) for i in range(len(headers))]

    def line(cells):
        parts = []
        for i, (cell, width) in enumerate(zip(cells, widths)):
            parts.append(cell.rjust(width) if i in (0, 4) else cell.ljust(width))
        return "  ".join(parts)

    rule = "-" * (sum(widths) + 2 * (len(widths) - 1))
    total = sum(e.amount for e in expenses)
    return "\n".join(
        [line(headers), rule, *(line(r) for r in rows), rule, f"{len(rows)} expense(s) | Total: {money(total)}"]
    )


def format_breakdown(title: str, totals: dict) -> str:
    """Bar-chart style breakdown for {label: amount}."""
    if not totals:
        return "No expenses to summarise."

    grand = sum(totals.values())
    top = max(totals.values())
    label_w = max(len(label) for label in totals)
    lines = [title, "-" * len(title)]
    for label, amount in totals.items():
        bar = "#" * max(1, round(amount / top * BAR_WIDTH))
        lines.append(f"{label.ljust(label_w)}  {money(amount):>12}  {amount / grand * 100:5.1f}%  {bar}")
    lines.append(f"{'TOTAL'.ljust(label_w)}  {money(grand):>12}")
    return "\n".join(lines)


def format_budget(status: dict) -> str:
    month, spent = status["month"], status["spent"]
    if status["budget"] is None:
        return f"No budget set. Spent in {month}: {money(spent)}.\nSet one with: python main.py budget 5000"

    percent = status["percent"]
    filled = min(BAR_WIDTH, round(percent / 100 * BAR_WIDTH))
    bar = "[" + "#" * filled + "-" * (BAR_WIDTH - filled) + "]"
    lines = [
        f"Budget for {month}",
        f"  Budget:    {money(status['budget'])}",
        f"  Spent:     {money(spent)} ({percent}%)",
        f"  {bar}",
    ]
    if status["remaining"] >= 0:
        lines.insert(3, f"  Remaining: {money(status['remaining'])}")
    else:
        lines.insert(3, f"  Over by:   {money(-status['remaining'])}")
    return "\n".join(lines)


def budget_alert(status: dict) -> str:
    """One-line warning, or an empty string when spending is comfortably within budget."""
    if status["budget"] is None:
        return ""
    if status["percent"] >= 100:
        return f"WARNING: you are over your {status['month']} budget by {money(-status['remaining'])}."
    if status["percent"] >= 80:
        return f"Heads up: {status['percent']}% of your {status['month']} budget is used."
    return ""
