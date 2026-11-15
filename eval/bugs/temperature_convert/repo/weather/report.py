from weather.units import f_to_c


def format_reading(city: str, fahrenheit: float) -> str:
    return f"{city}: {round(f_to_c(fahrenheit))}C"
