# Import utility functions to check for NaN (not a number) and infinite values
from math import isnan, isinf

# Import Mapping abstract base class to validate if input is dictionary-like
from collections.abc import Mapping

# Import NumPy for working with numerical data and NumPy-specific types
import numpy as np

# Define a function that takes a dictionary and sanitizes it
def sanitize_dict(data: dict) -> dict:
    """
    Remove keys with NaN, None, or infinite values,
    convert all keys to lowercase (optional),
    and ensure all values are native Python types.
    """

    # Helper function to check if a value is valid
    def is_valid_value(value):
        if value is None:  # Discard None values
            return False
        if isinstance(value, float) and (isnan(value) or isinf(value)):  # Discard NaN or infinite floats
            return False
        if isinstance(value, complex):  # Discard complex numbers
            return False
        return True  # Keep all other values

    # Helper function to convert NumPy-specific scalar types to native Python types
    def convert_value(value):
        if isinstance(value, (np.generic,)):  # If the value is a NumPy scalar (e.g., np.int64)
            return value.item()  # Convert to native Python type
        return value  # Return as-is if already a native type

    # Ensure input is a dictionary or mapping-like object
    if not isinstance(data, Mapping):
        raise ValueError("Input must be a dictionary or mapping.")

    # Create a new dictionary to store sanitized results
    sanitized = {}
    for key, value in data.items():  # Iterate through all key-value pairs in input
        if is_valid_value(value):  # Only process values that pass validation
            sanitized[key] = convert_value(value)  # Add the cleaned value to sanitized dict

    return sanitized  # Return the cleaned/sanitized dictionary
