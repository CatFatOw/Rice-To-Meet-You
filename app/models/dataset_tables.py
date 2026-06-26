from database import Base 
from sqlalchemy import Integer, Text, TIMESTAMP, Column, JSON, Boolean, Float, Date
from datetime import datetime, timedelta
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql.expression import text


# ----------------------------CORE DATASETS TABLES OF INTEREST (PROVIDED By RICE) ----------------------------

class CorePoiGeometry(Base):
    """Main postgres table for core_poi_geometry. 
    Please see reference doc for core_poi_geometry for detailed reference guide
    """

    __tablename__ = "core_poi_geometry"
    id = Column(Integer, primary_key=True, nullable=False)
    # Brands can be missing
    brands = Column(JSON, nullable=True)
    # Category of the brand, could also be missing
    category_tags = Column(JSON, nullable=True)
    city = Column(Text, nullable=False)
    closed_on = Column(Date, nullable=True)
    # The website of the brand etc
    domains = Column(JSON, nullable=True)

    # Starting with the geometry :)
    enclosed=Column(Boolean, nullable=False)
    geometry_type = Column(Text, nullable=False)
    includes_parking_lot = Column(Boolean, nullable=False)
    iso_country_code = Column(Text, nullable=False)
    is_synthetic = Column(Boolean, nullable=False)

    # Key position provided of the point of interest
    latitude = Column(Float, nullable=False)
    location_name = Column(Text, nullable=False)
    longitude = Column(Float, nullable=False)
    # market/city idk why its called market
    market = Column(Text, nullable=False)

    # Buisness identification codes 
    naics_code = Column(Integer, nullable=True)
    naics_code_2022 = Column(Integer, nullable=True)
    # Buisness opened on day
    opened_on = Column(Date, nullable=True)
    open_hours = Column(JSON, nullable=True)

    # Placekeys are used to 
    #A Placekey itself is a unique identifier assigned to a physical location or business.
    # # PLACEKEY = the current location's unique ID
    # PARENT_PLACEKEY = the unique ID of the larger location that contains it (if any)
    parent_placekey = Column(Text, nullable=True)
    phone_number = Column(Text, nullable=True)
    placekey = Column(Text, nullable=False)

    # Type of polygon (mask of the polygon of the building)
    polygon_class = Column(Text, nullable=False)
    # The actual coordinates of the polygon :)
    polygon_wkt = Column(Text, nullable=False)
    # postal code
    postal_code = Column(Text, nullable=False)
    # tx, ca, id
    region = Column(Text, nullable=False)
    # SafeGraph's own unique identifier for a place (POI).
    safegraph_place_id = Column(Text, nullable=False)
    store_id = Column(Text, nullable=True)
    street_address = Column(Text, nullable=False)
    sub_category = Column(Text, nullable=False)
    sub_category_2022 = Column(Text, nullable=False)
    top_category = Column(Text, nullable=False)
    top_category_2022 = Column(Text, nullable=False)
    tracking_closed_since = Column(Date, nullable=True)
    website = Column(Text, nullable=True)
    wkt_area_sq_meters = Column(Float, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class DailySpendBrandState(Base):
    """Table for the Daily Spend Brand and State dataset.
    For more detailed guide, please refer to the reference .md file 
    """

    __tablename__ = "daily_spend_brand_state_rice"

    id = Column(Integer, primary_key=True, nullable=False)

    # Unique identifier assigned to a brand
    brand_id = Column(Integer, nullable=False)

    # Name of the business/brand
    brand_name = Column(Text, nullable=False)

    # Metropolitan market where spending occurred
    market = Column(Text, nullable=False)

    # Estimated consumer spending amount
    spend_amount = Column(Float, nullable=False)

    # Two-letter state abbreviation
    state_abbr = Column(Text, nullable=False)

    # Estimated number of daily transactions (may be normalized)
    trans_count = Column(Float, nullable=False)

    # Date of the transaction data
    trans_date = Column(Date, nullable=False)

    # Dataset release/version
    version = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))



class DailyWeatherRice(Base):
    """Table for the daily weather rice dataset. One of the most crucial datasets for our task. For more detailed guides, please refer 
    to the reference guide"""

    __tablename__ = "daily_weather_rice"
    id = Column(Integer, nullable=False, primary_key=True)
    # The average daily dew point (moisture)
    average_dew_point_f = Column(Float, nullable=False)
    # the relative humidity in %
    average_relative_humidity = Column(Float, nullable=False)
    #average atmospheric pressure (millibars)
    average_sea_level_pressure_millibars = Column(Float, nullable=False)
    #average daily temp in C
    average_temperature_c = Column(Float, nullable=False)
    # average visibility 
    average_visibility_km = Column(Float, nullable=False)
    # average wind speed (knots)
    average_wind_speed_knots = Column(Float, nullable=False)
    #weather station/city identify
    city_location_identifier = Column(Text, nullable=False)
    #Cooling indicator (higher = more AC demand)
    cooling_degree_days_c = Column(Float, nullable=False)
    # Heating demand indicator (metric to measure how much heating buildings need)
    heating_degree_days_c = Column(Float, nullable=False)
    # Max temperature /day
    max_temperature_c = Column(Float, nullable=False)
    # min temp/day
    min_temperature_c = Column(Float, nullable=False)
    # Daily precipitation (0 = trace, -1=None) in hundrets of mililiters
    precipitation = Column(Integer, nullable=False)
    valid_date = Column(Date, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class SpendPatternsRice(Base):
    """Implements the table for spending patterns rice;
      for more detailed information please refer to the markdown guides.
      """

    __tablename__ = "spend_patterns_rice"

    id = Column(Integer, nullable=False, primary_key=True)

    # Brand/business name
    brands = Column(Text, nullable=False)

    # Number of customers grouped by visit frequency
    bucketed_customer_frequency = Column(JSON, nullable=False)

    # Customer counts grouped by income bracket
    bucketed_customer_incomes = Column(JSON, nullable=False)

    # City where the business is located
    city = Column(Text, nullable=False)

    # Customer home city distribution
    customer_home_city = Column(JSON, nullable=False)

    # Number of observations by weekday
    day_counts = Column(JSON, nullable=False)

    # Country code
    iso_country_code = Column(Text, nullable=False)

    # Latitude of the business
    latitude = Column(Float, nullable=False)

    # Longitude of the business
    longitude = Column(Float, nullable=False)

    # Name of the physical location
    location_name = Column(Text, nullable=False)

    # Metropolitan market
    market = Column(Text, nullable=False)

    # Mean spend per customer grouped by visit frequency
    mean_spend_per_customer_by_frequency = Column(JSON, nullable=False)

    # Mean spending by income bracket
    mean_spend_per_customer_by_income = Column(JSON, nullable=False)

    # Median spending per customer
    median_spend_per_customer = Column(Float, nullable=False)

    # Median spending per transaction
    median_spend_per_transaction = Column(Float, nullable=False)

    # Business classification code
    naics_code = Column(Integer, nullable=False)

    # Total online spending
    online_spend = Column(Float, nullable=False)

    # Number of online transactions
    online_transactions = Column(Float, nullable=False)

    # Parent location identifier
    parent_placekey = Column(Text, nullable=True)

    # Unique physical location identifier
    placekey = Column(Text, nullable=False)

    # ZIP/postal code
    postal_code = Column(Text, nullable=False)

    # Estimated customer count
    raw_num_customers = Column(Float, nullable=False)

    # Estimated transaction count
    raw_num_transactions = Column(Float, nullable=False)

    # Estimated total spending
    raw_total_spend = Column(Float, nullable=False)

    # State/region abbreviation
    region = Column(Text, nullable=False)

    # Buy-now-pay-later service usage percentages
    related_buynowpaylater_service_pct = Column(JSON, nullable=True)

    # Cross-shopping with local brands
    related_cross_shopping_local_brands_pct = Column(JSON, nullable=True)

    # Cross-shopping with online merchants
    related_cross_shopping_online_merchants_pct = Column(JSON, nullable=True)

    # Cross-shopping with physical brands
    related_cross_shopping_physical_brands_pct = Column(JSON, nullable=True)

    # Cross-shopping with same-category brands
    related_cross_shopping_same_category_brands_pct = Column(JSON, nullable=True)

    # Delivery service usage percentages
    related_delivery_service_pct = Column(JSON, nullable=True)

    # Payment platform usage percentages
    related_payment_platform_pct = Column(JSON, nullable=True)

    # Rideshare service usage percentages
    related_rideshare_service_pct = Column(JSON, nullable=True)

    # Streaming/cable service overlap percentages
    related_streaming_cable_pct = Column(JSON, nullable=True)

    # Wireless carrier overlap percentages
    related_wireless_carrier_pct = Column(JSON, nullable=True)

    # Spending values by day in the date range
    spend_by_day = Column(JSON, nullable=False)

    # Spending totals grouped by weekday
    spend_by_day_of_week = Column(JSON, nullable=False)

    # Spending grouped by transaction intermediary
    spend_by_transaction_intermediary = Column(JSON, nullable=True)

    # Start date of spending period
    spend_date_range_start = Column(Date, nullable=False)

    # End date of spending period
    spend_date_range_end = Column(Date, nullable=False)

    # Percent spending change vs previous month
    spend_pct_change_vs_prev_month = Column(Float, nullable=True)

    # Percent spending change vs previous year
    spend_pct_change_vs_prev_year = Column(Float, nullable=True)

    # Average spend per transaction by day
    spend_per_transaction_by_day = Column(JSON, nullable=False)

    # Spend-per-transaction percentile distribution
    spend_per_transaction_percentiles = Column(JSON, nullable=False)

    # Street address of the business
    street_address = Column(Text, nullable=False)

    # Specific business category
    sub_category = Column(Text, nullable=False)

    # Broad business category
    top_category = Column(Text, nullable=False)

    # Transaction counts by intermediary
    transaction_intermediary = Column(JSON, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))

class StoreVisits(Base):
    """Table for the store visit dataset. For mroe detailed reference. please refer to the dataset models reference"""
    __tablename__ = "store_visits_rice"
    id = Column(Integer, primary_key=True, nullable=False)
    # Brand name 
    brand = Column(Text, nullable=False)
    # high level industry category
    category = Column(Text, nullable=False)
    # daily visits/day to the store 
    daily_visits = Column(Integer, nullable=False)
    # local calendar date for the vist 
    local_date = Column(Date, nullable=False)
    # market/city area
    market = Column(Text, nullable=False)
    # naic code 
    naics_code = Column(Integer, nullable=False)
    # buisness name 
    business_name = Column(Text, nullable=False)
    # State abbrb
    state = Column(Text, nullable=False)
    stock_exchange = Column(Text, nullable=True)
    stock_symbol = Column(Text, nullable=True)
    # store ID 
    store_id = Column(Text, nullable=False)
    sub_category = Column(Text, nullable=False)
    version_id = Column(Integer, nullable=False)
    created_at = Column(
    TIMESTAMP(timezone=True),
    nullable=False,
    server_default=text("CURRENT_TIMESTAMP"),
)

class UrbanHeatIndex(Base):
    """Table for the urban heat index dataset. For mroe detailed reference. please refer to the dataset models reference"""

    __tablename__ = "urban_heat_index"
    id = Column(Integer, primary_key=True, nullable=False)
    
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    market = Column(Text, nullable=False)
    # Point geometry stored in Well-Known Binary (WKB) hexadecimal format.
    #  Represents the exact geographic point.
    point_geometry = Column(Text, nullable=False)
    # urvan heat inteisty, higher values = greater urban heat impact
    uhi = Column(Integer, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
