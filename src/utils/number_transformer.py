import re


def persian_to_english(string: str) -> str:
    """
    Translates Persian numbers to English numbers.

    Args:
        `string (str)`: The string containing Persian numbers.

    Returns:
        `str`: The string with Persian numbers translated to English numbers.
    """
    persian_numbers = '۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩'
    english_numbers = '01234567890123456789'
    translation_table = str.maketrans(persian_numbers, english_numbers)
    return string.translate(translation_table)


def extract_number(string: str) -> float:
    """
    Extracts numbers from a string.

    Args:
        `string (str)`: Input string.

    Returns:
        `float`: The float number extracted from the string.
    """
    string = persian_to_english(string)
    match = re.search(r'[-+]?\d*\.\d+|\d+', string)
    if match:
        return float(match.group())
    else:
        return None