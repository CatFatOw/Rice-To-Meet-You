"""Business logic for final_visitor_table table """
import pandas as pd
from models.final_visitor_tables import VisitorData
from tqdm import tqdm


def load_data(final_visitor_df):
    """file loads data in parquet form and stored them as a list of VisitorData.
    To be processed by a repository file later. Takes quite a long time
    """
    df = pd.read_parquet(final_visitor_df)
    records = []

    for row in tqdm(df.itertuples(index=False), total=len(df)):
        records.append(
            VisitorData(
                city=row.CITY,
                local_date=row.LOCAL_DATE.date(),
                avg_daily_visits=row.AVERAGE_DAILY_VISITS,
                location_name=row.LOCATION_NAME,
                brand=row.BRAND,
                street_address=row.STREET_ADDRESS,
                latitude=row.LATITUDE,
                longitude=row.LONGITUDE,
            )
        )

    return records



