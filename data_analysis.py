# data_analysis.py

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

def get_spark_session():
    # Initialize Spark session for data analysis
    return SparkSession.builder \
        .appName("Data Analysis") \
        .config("spark.some.config.option", "some-value") \
        .getOrCreate()

# Initialize Spark session
spark = get_spark_session()

# Load CSV data into DataFrames
load_posting_df = spark.read.csv("load_posting.csv", header=True, inferSchema=True)
load_stop_df = spark.read.csv("load_stop.csv", header=True, inferSchema=True)

def analyze_load_data():
    """
    Analyze the dataset to provide insights about load types, stop types, cities with or without loads,
    and connected routes between cities.
    """
    
    # 1. Count loads by transport mode
    load_types = load_posting_df.groupBy("TRANSPORT_MODE").count().orderBy(F.desc("count"))
    print("Load counts by transport mode:")
    load_types.show()

    # 2. Count of loads by stop type (P for Pickup, D for Drop-off)
    stop_types = load_stop_df.groupBy("STOP_TYPE").count().orderBy(F.desc("count"))
    print("Stop counts by type (Pickup or Drop-off):")
    stop_types.show()

    # 3. Top cities with the most pickups and drop-offs
    pickup_cities = load_stop_df.filter(F.col("STOP_TYPE") == 'P').groupBy("CITY", "STATE").count().orderBy(F.desc("count"))
    dropoff_cities = load_stop_df.filter(F.col("STOP_TYPE") == 'D').groupBy("CITY", "STATE").count().orderBy(F.desc("count"))

    print("Top cities with the most pickups:")
    pickup_cities.show(10)  # Display top 10 pickup cities

    print("Top cities with the most drop-offs:")
    dropoff_cities.show(10)  # Display top 10 drop-off cities

    # 4. Cities with both pickups and drop-offs
    cities_with_both = load_stop_df.groupBy("CITY", "STATE").agg(
        F.sum(F.when(F.col("STOP_TYPE") == 'P', 1).otherwise(0)).alias("pickup_count"),
        F.sum(F.when(F.col("STOP_TYPE") == 'D', 1).otherwise(0)).alias("dropoff_count")
    ).filter(F.col("pickup_count") > 0).filter(F.col("dropoff_count") > 0)
    print("Cities with both pickups and drop-offs:")
    cities_with_both.show()

    # 5. Cities without any loads
    all_cities = load_stop_df.select("CITY", "STATE").distinct()
    cities_with_loads = all_cities.join(load_stop_df, on=["CITY", "STATE"], how="leftanti")
    print("Cities without any loads:")
    cities_with_loads.show()

    # 6. Average weight by transport mode and stop type
    avg_weight_by_type = load_posting_df.join(load_stop_df, on="LOAD_ID").groupBy("TRANSPORT_MODE", "STOP_TYPE").agg(
        F.avg("TOTAL_WEIGHT").alias("average_weight")
    )
    print("Average weight by transport mode and stop type:")
    avg_weight_by_type.show()

    # 7. Insights on load statuses
    load_status = load_posting_df.groupBy("POSTING_STATUS").count().orderBy(F.desc("count"))
    print("Load counts by posting status:")
    load_status.show()

    # 8. City Pairs with Active Routes (Origin-Destination pairs)
    # Join stop data to get origin-destination pairs for each LOAD_ID
    pickup_df = load_stop_df.filter(F.col("STOP_TYPE") == 'P').select("LOAD_ID", "CITY", "STATE")
    dropoff_df = load_stop_df.filter(F.col("STOP_TYPE") == 'D').select("LOAD_ID", "CITY", "STATE")

    # Renaming columns for clarity
    pickup_df = pickup_df.withColumnRenamed("CITY", "Origin_City").withColumnRenamed("STATE", "Origin_State")
    dropoff_df = dropoff_df.withColumnRenamed("CITY", "Dest_City").withColumnRenamed("STATE", "Dest_State")

    # Merge to find connected city pairs with routes
    city_pairs = pickup_df.join(dropoff_df, on="LOAD_ID").select("Origin_City", "Origin_State", "Dest_City", "Dest_State").distinct()
    print("City pairs with active transport routes:")
    city_pairs.show()

if __name__ == "__main__":
    analyze_load_data()
    spark.stop()
