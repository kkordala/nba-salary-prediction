from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col
from pyspark.sql.types import StructType, StructField, IntegerType

spark = SparkSession.builder \
    .appName("KafkaSparkBridge") \
    .getOrCreate()

# 1. Define schema
schema = StructType([
    StructField("x", IntegerType()),
    StructField("y", IntegerType())
])

# 2. Read from Kafka with "FailSafe" options
# failOnDataLoss=false prevents the crash if topics are reset
df = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "kafka:9092") \
    .option("subscribe", "raw-events") \
    .option("startingOffsets", "earliest") \
    .option("failOnDataLoss", "false") \
    .load()

# 3. Process data
json_df = df.selectExpr("CAST(value AS STRING)") \
    .select(from_json(col("value"), schema).alias("data")) \
    .select("data.*")

result_df = json_df.withColumn("sum", col("x") + col("y"))

# 4. Write to Kafka
query = result_df.selectExpr("CAST(NULL AS STRING) AS key", "to_json(struct(*)) AS value") \
    .writeStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "kafka:9092") \
    .option("topic", "processed-events") \
    .option("checkpointLocation", "/home/jovyan/work/checkpoints") \
    .trigger(processingTime='1 second') \
    .start()

query.awaitTermination()