"""
Pydantic schemas for geospatial and land use context.
"""

from typing import Optional
from pydantic import BaseModel, Field


class NearbyFeatureResponse(BaseModel):
    """A geographic feature found near a thermal observation."""

    feature_type: str = Field(..., description="Category, e.g. industrial, forest, farmland, road, building")
    name: Optional[str] = Field(None, description="Feature name if available")
    distance_m: Optional[float] = Field(None, description="Distance from observation in meters")
    osm_id: Optional[int] = Field(None, description="OpenStreetMap ID")
    osm_type: Optional[str] = Field(None, description="OSM element type (node, way, relation)")
    tags: dict[str, str] = Field(default_factory=dict, description="OSM raw tags")


class GeospatialResponse(BaseModel):
    """Geographic context around a specific location."""

    latitude: float = Field(..., description="Target latitude in WGS84")
    longitude: float = Field(..., description="Target longitude in WGS84")
    radius_m: float = Field(default=2000.0, description="Search radius in meters")
    industrial: list[NearbyFeatureResponse] = Field(default_factory=list, description="Nearby industrial facilities and flares")
    forests: list[NearbyFeatureResponse] = Field(default_factory=list, description="Nearby forests and vegetative cover")
    croplands: list[NearbyFeatureResponse] = Field(default_factory=list, description="Nearby farmlands and agricultural areas")
    roads: list[NearbyFeatureResponse] = Field(default_factory=list, description="Nearby roads and transport corridors")
    buildings: list[NearbyFeatureResponse] = Field(default_factory=list, description="Nearby buildings and built structures")
    source: str = Field(default="openstreetmap", description="Data source identifier")
