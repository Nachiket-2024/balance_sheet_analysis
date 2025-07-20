from math import isnan, isinf
from collections.abc import Mapping
import numpy as np

def sanitize_dict(data: dict) -> dict:
    """
    Remove keys with NaN, None, or infinite values,
    convert all keys to lowercase (optional),
    and ensure all values are native Python types.
    """

    def is_valid_value(value):
        if value is None:
            return False
        if isinstance(value, float) and (isnan(value) or isinf(value)):
            return False
        if isinstance(value, complex):
            return False
        return True

    def convert_value(value):
        # Convert NumPy scalars to native Python types
        if isinstance(value, (np.generic,)):
            return value.item()
        return value

    if not isinstance(data, Mapping):
        raise ValueError("Input must be a dictionary or mapping.")

    sanitized = {}
    for key, value in data.items():
        if is_valid_value(value):
            sanitized[key] = convert_value(value)

    return sanitized
