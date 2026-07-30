from collections.abc import Mapping
from math import isinf, isnan

import numpy as np


def sanitize_dict(data: dict) -> dict:
    """
    Strips None/NaN/infinite/complex values and converts numpy scalar types
    (e.g. np.float64) to native Python ones, so a yfinance DataFrame row can
    be passed straight into a SQLAlchemy model constructor. Ported unchanged
    from the pre-migration repo (to_arrange/backend/utils/sanitize_fields.py).
    """

    def is_valid_value(value) -> bool:
        if value is None:
            return False
        if isinstance(value, float) and (isnan(value) or isinf(value)):
            return False
        return not isinstance(value, complex)

    def convert_value(value):
        return value.item() if isinstance(value, np.generic) else value

    if not isinstance(data, Mapping):
        raise ValueError("Input must be a dictionary or mapping.")

    return {key: convert_value(value) for key, value in data.items() if is_valid_value(value)}
