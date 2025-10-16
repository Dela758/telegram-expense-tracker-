import re

def parse_expense_message(text):
    # Example: "spent 50 on food", "bought lunch 12"
    pattern = re.compile(r"(?i)(spent|paid|bought)?\s*(\d+(\.\d{1,2})?)\s*(on|for)?\s*(\w+)?")
    match = pattern.search(text)
    if not match:
        return None
    amount = float(match.group(2))
    category = match.group(5) or "misc"
    return {"amount": amount, "category": category.lower()}
