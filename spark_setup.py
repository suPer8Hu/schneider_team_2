from pyspark.sql import SparkSession

def get_spark_session():
    spark = SparkSession.builder \
        .appName("Schneider Freight Search") \
        .config("spark.some.config.option", "config-value") \
        .getOrCreate()
    return spark
