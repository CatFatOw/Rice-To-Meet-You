# Core Dataset Reference Guide: `core_poi_geometry`

## Overview

`core_poi_geometry` contains point-of-interest location and geometry data.  
For the Rice FIFA 2026 Hackathon, this dataset is useful for identifying places, buildings, parking lots, business categories, and spatial risk zones around host-city infrastructure.

## Most Useful Columns for FIFA HeatSafe / Urban Heat Resilience Idea

| Column | Why It Matters |
|---|---|
| `latitude` / `longitude` | Core coordinates for mapping POIs onto heat-risk grids |
| `polygon_wkt` | Building/area footprint geometry for spatial analysis |
| `wkt_area_sq_meters` | Approximate physical size of the POI footprint |
| `includes_parking_lot` | Parking lots may contribute to urban heat island effects |
| `location_name` | Human-readable POI name for maps and dashboards |
| `top_category` / `sub_category` | Helps classify hospitals, stores, transit places, food, recreation, etc. |
| `naics_code` | Standard business category code for filtering POI types |
| `street_address`, `city`, `region`, `postal_code` | Useful for user-facing location context |
| `open_hours` | Can help estimate when cooling/resource locations are available |
| `closed_on`, `opened_on` | Helps avoid using outdated or inactive POIs |

---

## Column Reference

| Column | SQLAlchemy Type | Example | Explanation |
|---|---|---|---|
| `id` | `Integer` | `1` | Internal database primary key |
| `brands` | `JSON` | `[{"safegraph_brand_name": "Enterprise"}]` | Brand metadata if the POI belongs to a known brand |
| `category_tags` | `JSON` | `["Car Rental", "Truck Rental"]` | Extra category labels for the POI |
| `city` | `Text` | `"Houston"` | City where the POI is located |
| `closed_on` | `Date` | `"2022-05-01"` | Date the POI closed, if known |
| `domains` | `JSON` | `["enterprise.com"]` | Website domains associated with the POI |
| `enclosed` | `Boolean` | `false` | Whether the POI is inside an enclosed structure |
| `geometry_type` | `Text` | `"POLYGON"` | Type of geometry provided |
| `includes_parking_lot` | `Boolean` | `true` | Whether the polygon includes a parking lot |
| `iso_country_code` | `Text` | `"US"` | Country code |
| `is_synthetic` | `Boolean` | `false` | Whether the record was synthetically generated |
| `latitude` | `Float` | `29.7604` | Latitude coordinate of the POI |
| `longitude` | `Float` | `-95.3698` | Longitude coordinate of the POI |
| `location_name` | `Text` | `"Rice Stadium"` | Name of the place or business |
| `market` | `Text` | `"Houston"` | Market area associated with the POI |
| `naics_code` | `Integer` | `722511` | Business classification code |
| `naics_code_2022` | `Integer` | `722511` | Updated 2022 NAICS classification |
| `opened_on` | `Date` | `"2018-05-14"` | Date the POI opened, if known |
| `open_hours` | `JSON` | `{"Mon": [["09:00", "17:00"]]}` | Operating hours |
| `parent_placekey` | `Text` | `"abc-123@xyz"` | Placekey of a larger containing location |
| `placekey` | `Text` | `"223-222@8fc-9qc-9j9"` | Unique location identifier |
| `phone_number` | `Text` | `"+17135551234"` | Phone number of the POI |
| `polygon_class` | `Text` | `"OWNED_POLYGON"` | Classification of the polygon geometry |
| `polygon_wkt` | `Text` | `"POLYGON ((...))"` | Full polygon geometry in WKT format |
| `postal_code` | `Text` | `"77005"` | ZIP/postal code |
| `region` | `Text` | `"TX"` | State or region abbreviation |
| `safegraph_place_id` | `Text` | `"sg:abc123"` | SafeGraph's internal POI identifier |
| `store_id` | `Text` | `"1234"` | Store identifier if available |
| `street_address` | `Text` | `"6100 Main St"` | Street address |
| `sub_category` | `Text` | `"Full-Service Restaurants"` | More specific business category |
| `sub_category_2022` | `Text` | `"Full-Service Restaurants"` | Updated 2022 subcategory |
| `top_category` | `Text` | `"Food Services and Drinking Places"` | Broad business category |
| `top_category_2022` | `Text` | `"Food Services and Drinking Places"` | Updated 2022 top category |
| `tracking_closed_since` | `Date` | `"2023-01-01"` | Date SafeGraph started tracking the POI as closed |
| `website` | `Text` | `"https://example.com"` | Website URL |
| `wkt_area_sq_meters` | `Float` | `135.7` | Area of the polygon footprint in square meters |

---

## Notes for the Hackathon

This table is especially useful for building a map-based urban heat dashboard.

Possible uses:

1. Map POIs onto predicted heat-risk zones.
2. Identify high-risk places near stadiums, hotels, transit, parking lots, and commercial corridors.
3. Filter by categories such as healthcare, food, retail, transit, or recreation.
4. Detect large hardscape areas using `polygon_wkt`, `wkt_area_sq_meters`, and `includes_parking_lot`.
5. Recommend cooling interventions near clusters of high-risk POIs.