"""Display-string parsers for heatmap metric values.

Port of `services/parsers.ts`. Every `individual_metrics` value arrives as a
formatted string carrying its own unit, so these pull the number back out and
return None when the string does not match the expected shape.
"""

from __future__ import annotations

import re

# "13°C", "-2.5 °C"  (case-insensitive on the C)
_TEMPERATURE_RE = re.compile(r"^(-?\d+(?:\.\d+)?)\s*°C$", re.IGNORECASE)

# "49.4%", "80 %"
_PERCENTAGE_RE = re.compile(r"^(-?\d+(?:\.\d+)?)\s*%$")


def parse_temperature(value: str) -> float | None:
    """Parse a temperature string such as "13°C" into 13.0.

    Returns None when the value is invalid.
    """
    match = _TEMPERATURE_RE.match(value.strip())
    return float(match.group(1)) if match else None


def parse_percentage(value: str) -> float | None:
    """Parse a percentage string such as "49.4%" into 49.4.

    Returns None when the value is invalid.
    """
    match = _PERCENTAGE_RE.match(value.strip())
    return float(match.group(1)) if match else None


if __name__ == "__main__":
    assert parse_temperature("13°C") == 13
    assert parse_temperature("-2.5 °C") == -2.5
    assert parse_percentage("49.4%") == 49.4
    assert parse_percentage("80 %") == 80
    assert parse_temperature("13") is None
    assert parse_percentage("") is None
    print("parsers ok")