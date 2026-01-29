from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    from_json, col, sqrt, pow, coalesce, lit, to_json, struct, exp, udf

)
from pyspark.sql.types import ArrayType, StructType, StructField, DoubleType, FloatType, StringType
from pyspark.ml import PipelineModel
import sys
import os


spark = SparkSession.builder \
    .appName("NBA-Salary-Prediction") \
    .config("spark.sql.shuffle.partitions", "4") \
    .config("spark.sql.streaming.metricsEnabled", "true") \
    .getOrCreate()


MODEL_DIR = "/home/jovyan/models"
DATA_DIR = "/home/jovyan/data"
try:
    huber_model = PipelineModel.load(os.path.join(MODEL_DIR, "huber_model"))
    ridge_model = PipelineModel.load(os.path.join(MODEL_DIR, "ridge_model"))
    rf_model    = PipelineModel.load(os.path.join(MODEL_DIR, "rf_model"))
    raw_data = spark.read.parquet(os.path.join(DATA_DIR,"processed/clean_nba.parquet"))
except Exception as e:
    spark.stop()
    print(f"CRITICAL: Failed to load models: {str(e)}", file=sys.stderr)
    sys.exit(1)


schema = StructType([
    StructField("age", FloatType(), True),
    StructField("ppg", FloatType(), True),
    StructField("fg_avg", FloatType(), True),
    StructField("three_pt_avg", FloatType(), True),
    StructField("ft_avg", FloatType(), True),
    StructField("apg", FloatType(), True),
    StructField("rpg", FloatType(), True),
    StructField("spg", FloatType(), True),
    StructField("bpg", FloatType(), True),
    StructField("mpg", FloatType(), True)
])


raw_stream = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "kafka:9092") \
    .option("subscribe", "raw-events") \
    .option("startingOffsets", "latest") \
    .option("failOnDataLoss", "false") \
    .option("maxOffsetsPerTrigger", 10000) \
    .option("fetchOffset.retry.interval.ms", "500") \
    .load()


json_df = raw_stream.selectExpr("CAST(value AS STRING) as json_str") \
    .select(from_json(col("json_str"), schema).alias("data")) \
    .select("data.*") \
    .filter(col("age").isNotNull()) \
    .withColumn("salary", lit(0.0).cast("double"))


predictions = json_df \
    .transform(lambda df: huber_model.transform(df).withColumn("prediction", exp(col("prediction")) + 1).withColumnRenamed("prediction", "pred_huber").drop("raw_features","features","salary_log")) \
    .transform(lambda df: ridge_model.transform(df).withColumn("prediction", exp(col("prediction")) + 1).withColumnRenamed("prediction", "pred_ridge").drop("raw_features","features","salary_log")) \
    .transform(lambda df: rf_model.transform(df).withColumn("prediction", exp(col("prediction")) + 1).withColumnRenamed("prediction", "pred_rf").drop("raw_features","features","salary_log"))


n = 3.0
predictions = predictions \
    .withColumn("prediction_avg", (col("pred_huber") + col("pred_ridge") + col("pred_rf")) / n) \
    .withColumn("variance", 
        (pow(col("pred_huber") - col("prediction_avg"), 2) +
         pow(col("pred_ridge") - col("prediction_avg"), 2) +
         pow(col("pred_rf") - col("prediction_avg"), 2)) / (n - 1)
    ) \
    .withColumn("prediction_std", sqrt(col("variance"))) \
    .withColumn("prediction_std", coalesce(col("prediction_std"), lit(0.0)))  # Handle zero-variance

broadcast_data = spark.sparkContext.broadcast(
    raw_data.select("name","positions","team","season","salary","slug").collect()
)

def find_similar_players(pred_salary):
    """Find 3 players with closest salaries to prediction"""
    if pred_salary is None:
        return []
    
    players = broadcast_data.value

    sorted_players = sorted(
        players, 
        key=lambda p: abs(p.salary - pred_salary) if p.salary else float('inf')
    )[:3]
    
    return [
        {
            "name": p.name,
            "positions": p.positions,
            "team": p.team,
            "season": p.season,
            "salary": p.salary,
            "slug": p.slug
        }
        for p in sorted_players
    ]



similar_schema = ArrayType(StructType([
    StructField("name", StringType(), True),
    StructField("positions", StringType(), True),
    StructField("team", StringType(), True),
    StructField("season", StringType(), True),
    StructField("salary", DoubleType(), True),
    StructField("slug", StringType(), True)
]))

find_similar_udf = udf(find_similar_players, similar_schema)

predictions = predictions.withColumn("similar_players", find_similar_udf(col("prediction_avg")))


output = predictions.select(
    lit(None).cast(StringType()).alias("key"),
    to_json(struct(
        col("prediction_avg").alias("avg"),
        col("prediction_std").alias("std"),
        col("similar_players")
    )).alias("value")
)


query = output.writeStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "kafka:9092") \
    .option("topic", "processed-events") \
    .option("checkpointLocation", "/home/jovyan/work/checkpoints") \
    .option("failOnDataLoss", "false") \
    .trigger(processingTime="1 second") \
    .outputMode("append") \
    .start()
query.awaitTermination()
