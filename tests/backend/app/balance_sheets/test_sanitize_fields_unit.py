import math

import pytest
from backend.app.balance_sheets.sanitize_fields import sanitize_dict


def test_drops_none_nan_inf_and_complex_values():
    result = sanitize_dict(
        {
            "keep": 1.5,
            "none_value": None,
            "nan_value": math.nan,
            "inf_value": math.inf,
            "neg_inf_value": -math.inf,
            "complex_value": 1 + 2j,
        }
    )
    assert result == {"keep": 1.5}


def test_converts_numpy_scalars_to_native_python_types():
    import numpy as np

    result = sanitize_dict({"a": np.float64(3.5), "b": np.int64(7)})
    assert result == {"a": 3.5, "b": 7}
    assert isinstance(result["a"], float)
    assert isinstance(result["b"], int)


def test_raises_on_non_mapping_input():
    with pytest.raises(ValueError, match="dictionary or mapping"):
        sanitize_dict([("a", 1)])  # type: ignore[arg-type]
