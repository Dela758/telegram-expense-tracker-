import requests

API_URL = "https://api.exchangerate.host/latest"

# Base is always USD
rates_cache = {}

def get_rate(target_currency):
    target_currency = target_currency.upper()
    if target_currency in rates_cache:
        return rates_cache[target_currency]
    res = requests.get(f"{API_URL}?base=USD")
    data = res.json()
    rate = data["rates"].get(target_currency, 1.0)
    rates_cache[target_currency] = rate
    return rate

def convert(amount, from_currency, to_currency):
    rate_from = get_rate(from_currency)
    rate_to = get_rate(to_currency)
    return amount / rate_from * rate_to
