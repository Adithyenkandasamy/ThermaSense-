"""Land-cover lookup placeholder.

The MVP returns conservative contextual labels until an open land-cover dataset is wired in.
"""


def lookup_land_cover(latitude: float, longitude: float) -> str:
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return "UNKNOWN"
    return "UNKNOWN"
