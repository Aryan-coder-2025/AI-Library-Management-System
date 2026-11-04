"""
ISBN validation, normalization, and conversion utilities.
Supports ISBN-10 and ISBN-13 checksum validation, formatting normalization,
and bidirectional conversion from ISBN-10 to canonical ISBN-13.
"""
import re
from typing import Optional


def clean_isbn_string(raw: str) -> str:
    """Removes all whitespace and hyphens, converting to uppercase."""
    if not raw:
        return ""
    return re.sub(r"[\s\-]+", "", raw.strip()).upper()


def validate_isbn10_checksum(clean_isbn10: str) -> bool:
    """
    Validates the modulus 11 checksum of a 10-character ISBN string.
    Weights are 10 down to 1.
    """
    if len(clean_isbn10) != 10:
        return False
    
    total = 0
    for i in range(9):
        if not clean_isbn10[i].isdigit():
            return False
        total += int(clean_isbn10[i]) * (10 - i)
    
    last_char = clean_isbn10[9]
    if last_char == "X":
        check_val = 10
    elif last_char.isdigit():
        check_val = int(last_char)
    else:
        return False
    
    total += check_val
    return total % 11 == 0


def validate_isbn13_checksum(clean_isbn13: str) -> bool:
    """
    Validates the modulus 10 checksum of a 13-digit ISBN string.
    Alternating weights are 1 and 3.
    """
    if len(clean_isbn13) != 13 or not clean_isbn13.isdigit():
        return False
    
    total = sum(
        int(clean_isbn13[i]) * (1 if i % 2 == 0 else 3)
        for i in range(12)
    )
    check_digit = (10 - (total % 10)) % 10
    return int(clean_isbn13[12]) == check_digit


def isbn10_to_isbn13(isbn10: str) -> Optional[str]:
    """
    Converts a valid ISBN-10 string to its canonical 13-digit ISBN-13 representation.
    Prepends '978' and calculates the modulus 10 check digit.
    Returns None if input ISBN-10 is invalid.
    """
    clean = clean_isbn_string(isbn10)
    if not validate_isbn10_checksum(clean):
        return None
    
    prefix9 = "978" + clean[:9]
    total = sum(
        int(prefix9[i]) * (1 if i % 2 == 0 else 3)
        for i in range(12)
    )
    check_digit = (10 - (total % 10)) % 10
    return prefix9 + str(check_digit)


def parse_and_normalize_isbn(raw: str) -> Optional[str]:
    """
    Parses arbitrary ISBN input (hyphenated, unhyphenated, spaced, ISBN-10, or ISBN-13).
    - If valid ISBN-13, returns the clean 13-digit unhyphenated string.
    - If valid ISBN-10, converts and returns the clean 13-digit unhyphenated string.
    - If invalid or checksum fails, returns None.
    """
    clean = clean_isbn_string(raw)
    if not clean:
        return None
    
    if len(clean) == 13:
        if validate_isbn13_checksum(clean):
            return clean
        return None
    
    if len(clean) == 10:
        return isbn10_to_isbn13(clean)
    
    return None

