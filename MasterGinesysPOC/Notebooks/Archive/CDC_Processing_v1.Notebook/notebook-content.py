# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "849ada4d-ae5f-474f-bb0c-bc3244493216",
# META       "default_lakehouse_name": "LandingLayer",
# META       "default_lakehouse_workspace_id": "4804794c-8f08-4488-909a-10692b6ff9a4",
# META       "known_lakehouses": [
# META         {
# META           "id": "e0900400-854c-482c-9e69-df5803cec4c1"
# META         },
# META         {
# META           "id": "849ada4d-ae5f-474f-bb0c-bc3244493216"
# META         },
# META         {
# META           "id": "96a72669-9e55-4ced-ab59-934fc239ed52"
# META         },
# META         {
# META           "id": "28f7e917-3e52-4fa7-89cf-1b43064b4a19"
# META         }
# META       ]
# META     }
# META   }
# META }

# MARKDOWN ********************

# ##### **Import Libraries**

# CELL ********************

from pyspark.sql.functions import col, lit,udf,explode, when ,regexp_extract,current_timestamp, row_number, desc, from_json, from_unixtime, unix_timestamp
from delta.tables import DeltaTable
from pyspark.sql.functions import encode, base64
import base64
from decimal import Decimal
from pyspark.sql.types import StructType, StructField, StringType, ArrayType, LongType,IntegerType, TimestampType,DecimalType,DateType
from datetime import datetime
import pandas as pd
from pyspark.sql import functions as F
from pyspark.sql.window import Window
import logging
import pytz

# Configure logging
logging.basicConfig(level=logging.ERROR)

# Define IST timezone
ist = pytz.timezone('Asia/Kolkata')

#Path
filepath="abfss://Ginesys1@onelake.dfs.fabric.microsoft.com/BronzeLayer.Lakehouse/Tables/"


# Sets the datetime rebase mode to "LEGACY" when writing Parquet files.
# This ensures that Spark uses the old Julian calendar for dates before 1582, 
# matching the behavior of earlier Spark versions. 
# Use this setting to avoid date shifts when migrating legacy data or working with historical timestamps.
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInWrite", "LEGACY")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ##### **Define Variables**

# CELL ********************

landinglayerpath = "abfss://GinesysCDCPoc@onelake.dfs.fabric.microsoft.com/LandingLayer.Lakehouse/"
landinglayertablepath = f"{landinglayerpath}Tables/"
bronzelayerpath = "abfss://GinesysCDCPoc@onelake.dfs.fabric.microsoft.com/BronzeLayer.Lakehouse/"
bronzelayertablepath = f"{bronzelayerpath}Tables/"
masterlakehousepath="abfss://MasterGinesys@onelake.dfs.fabric.microsoft.com/OnBoardingLakehouse.Lakehouse/"
masterlakehousetablepath = f"{masterlakehousepath}Tables/"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ##### **Get Snapshot Ingestion Timestamp Range**

# CELL ********************

# df_configMin = spark.sql("SELECT MaxIngestionTimestamp AS MinTimestamp FROM LandingLayer.config_ingestion")
# df_configMax = spark.sql("SELECT max(ingestion_datetime) AS MaxTimestamp FROM LandingLayer.sc_cdcpoc_snapshot_kql")

df_configMin = spark.sql("SELECT MinIngestionTimestamp AS MinTimestamp FROM LandingLayer.config_ingestion")
df_configMax = spark.sql("SELECT DATEADD(minute,10,MinIngestionTimestamp) AS MaxTimestamp FROM LandingLayer.config_ingestion")

# df_configMax = spark.sql("SELECT DATEADD(hour,1,MinIngestionTimestamp) AS MaxTimestamp FROM LandingLayer.config_ingestion")
# df_configMin = spark.sql("SELECT min(ingestion_datetime) AS MinTimestamp FROM LandingLayer.sc_cdcpoc_snapshot_kql")
# df_configMax = spark.sql("SELECT max(ingestion_datetime) AS MaxTimestamp FROM LandingLayer.sc_cdcpoc_snapshot_kql")

# Collect min and max ingestion timestamps
configMin_row = df_configMin.collect()[0]
configMax_row = df_configMax.collect()[0]

min_time = configMin_row["MinTimestamp"]
max_time = configMax_row["MaxTimestamp"]

print(min_time)
print(max_time)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ##### **Get Streaming Snapshot**

# CELL ********************

query = f"select * from LandingLayer.sc_cdcpoc_snapshot_kql where ingestion_datetime > '{min_time}' and ingestion_datetime <= '{max_time}'"
dfsnapshot = spark.sql(query)
display(dfsnapshot.count())

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ##### **Define Decode Function**

# CELL ********************


# Function to decode Base64 and convert to decimal
def convert_pricefactor(value, scale):
    try:
        if value is None:
            return None  # Handle nulls
        if not isinstance(value, str):
            return value  # Skip decoding, already a numeric type

        logging.info("Decoder is ready to decode")
        decoded_bytes = base64.b64decode(value)
        decoded_number = int.from_bytes(decoded_bytes, byteorder='big')

        decimal_value = Decimal(decoded_number) / (10 ** scale)
        return str(decimal_value.quantize(Decimal(f"1.{'0' * scale}")))
    except Exception as e:
        logging.error(f"Decoding error for value {value}: {e}")
        return None


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ##### **Define  Schema**

# CELL ********************

# Define the schema for the JSON data
payloadschema = StructType([
    StructField("before", StringType(), True),
    StructField("after",StringType(), True),
    StructField("source", StructType([
        StructField("version", StringType(), True),
        StructField("connector", StringType(), True),
        StructField("name", StringType(), True),
        StructField("ts_ms", LongType(), True),
        StructField("snapshot", StringType(), True),
        StructField("db", StringType(), True),
        StructField("sequence", StringType(), True),
        StructField("ts_us", LongType(), True),
        StructField("ts_ns", LongType(), True),
        StructField("schema", StringType(), True),
        StructField("table", StringType(), True),
        StructField("txId", LongType(), True),
        StructField("lsn", LongType(), True),
        StructField("xmin", StringType(), True)
    ]), True),
    StructField("transaction", StringType(), True),
    StructField("op", StringType(), True),
    StructField("ts_ms", LongType(), True),
    StructField("ts_us", LongType(), True),
    StructField("ts_ns", LongType(), True)
])


# Define the schema for the 'fields' array
schema = StructType([
    StructField("fields", ArrayType(StructType([
        StructField("field", StringType(), True),
        StructField("type", StringType(), True),
        StructField("optional", StringType(), True),
        StructField("fields", ArrayType(StructType([  # Recursive nesting
            StructField("field", StringType(), True),
            StructField("type", StringType(), True),
            StructField("optional", StringType(), True),
            StructField("name", StringType(), True),
            StructField("parameters", StructType([  # Parameters as a StructType
                StructField("scale", StringType(), True),
                StructField("connect.decimal.precision", StringType(), True)
            ]), True)
        ])), True)
    ])), True)
])

# Parse the JSON string in the Payload column
# parsed_dfrawdata = dfsnapshot.withColumn("json_data", from_json(col("Payload"), schema))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ##### **Extract Payload Data**

# CELL ********************


# Parse the JSON string in the Payload column
parsed_dfrawdata = dfsnapshot.withColumn("json_data", from_json(col("Payload"), payloadschema))

# Extract the necessary fields
extracted_dfrawdata = parsed_dfrawdata.select(
    col("json_data.op").alias("operation"),
    col("json_data.source.schema").alias("schema"),
    col("json_data.source.table").alias("table"),
    col("json_data.source.ts_ms").alias("time_stamp"),
    col("json_data.after").alias("AfterRecord"),
    col("json_data.before").alias("BeforeRecord")
)

extracted_dfrawdata.createOrReplaceTempView("vw_extractedrawdata")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# extracted_dfrawdata.printSchema()

# display(extracted_dfrawdata.limit(1))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ##### **Extract Payload Schema**

# CELL ********************

# Step 1: Extract Only Required Fields from JSON
parsed_dfrawdata = dfsnapshot.withColumn(
    "table_name", from_json(col("Payload"), payloadschema)["source"]["table"]
).withColumn(
    "change_timestamp", from_json(col("Payload"), payloadschema)["ts_ms"]
).withColumn(
    "json_schema", from_json(col("schema"), schema)
).withColumn(
    "ingestion_datetime", col("ingestion_datetime")  # Corrected this part
).select("table_name", "change_timestamp","ingestion_datetime", "json_schema")  # Drop early

# Step 2: Use Window Function to Get Latest Record Per Table
window_spec = Window.partitionBy("table_name").orderBy(desc("change_timestamp"))

latest_changes = parsed_dfrawdata.withColumn(
    "row_num", row_number().over(window_spec)
).filter(
    col("row_num") == 1
).drop("row_num")  # Drop computed column

# Step 2: Display Results
# display(latest_changes)


# Step 3: Explode the top-level 'fields' array
latest_changes = latest_changes.withColumn("field_info", explode(col("json_schema.fields")))

# Step 4: Extract Top-Level Fields
top_level_fields = latest_changes.select(
    col("table_name"),
    col("field_info.field").alias("FieldName"),
    col("field_info.type").alias("FieldType"),
    col("field_info.optional").alias("Optional"),
    col("field_info.fields").alias("s")
)

# Step 5: Handle Nested Fields
nested_df = top_level_fields.filter(col("s").isNotNull())
exploded_nested_df = nested_df.withColumn("nested_field_info", explode(col("s")))

# display(exploded_nested_df)
# exploded_nested_df.printSchema()

nested_fields = exploded_nested_df.select(
    col("table_name").alias("TableName"),
    col("FieldName").alias("ParentFieldName"),
    col("nested_field_info.field").alias("Name"),
    col("nested_field_info.type").alias("FieldType"),
    col("nested_field_info.name").alias("Description"),
    col("nested_field_info.parameters.scale").alias("Scale"),
    col("nested_field_info.parameters.`connect.decimal.precision`").alias("Precision")
)

# Display the results
# display(nested_fields)

# Extract text from the right side after the last period '.'
nested_fields = nested_fields.withColumn(
    "Description", 
    regexp_extract(col("Description"), r"([^\.]+)$", 0)
)

# display(nested_fields)
#  Apply conditional logic to set FieldType based on the conditions
nested_fields = nested_fields.withColumn(
    "FieldType",
    when(
        (col("Description").like("%Decimal%")) & 
        (col("Scale").isNotNull()) & 
        (col("Precision").isNotNull()), 
        col("Description")
    ).when(
        col("Description").like("%Timestamp%"),
        col("Description")
    ).otherwise(col("FieldType"))
)

# Cast Scale and Precision to IntegerType
nested_fields = nested_fields.withColumn(
    "Scale", col("Scale").cast(IntegerType())
).withColumn(
    "Precision", col("Precision").cast(IntegerType())
)

# display(nested_fields)
after_fields = nested_fields.filter(col("ParentFieldName") == "after") \
    .select("TableName", "Name", "FieldType","Description","Scale","Precision") 


# Remove duplicates before exploding (if needed)
after_fields = after_fields.dropDuplicates()

# display(after_fields)



# # Assuming you have a Spark DataFrame 'df'
# filtered_df = after_fields.filter(after_fields['TableName'].like('%invgrp%'))

# # Show the filtered DataFrame
# display(filtered_df)



# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ##### **Schema Mapping**

# CELL ********************

from pyspark.sql.types import StructType, StructField, StringType, LongType, DecimalType, TimestampType

# Extract the fields from the 'after_fields' DataFrame
fields = after_fields.select("TableName", "Name", "FieldType", "Scale", "Precision").collect()

# Map field types to PySpark data types
type_mapping = {
    "string": StringType(),
    "int64": LongType(),
    "long": LongType(),
    "Decimal": lambda scale, precision: DecimalType(precision, scale),
    "Timestamp": TimestampType()
}

# Dictionary to store schema per table
table_schemas = {}

for field in fields:
    table_name = field["TableName"]
    field_name = field["Name"]
    field_type = field["FieldType"]
    scale = field["Scale"]
    precision = field["Precision"]

    # Determine the data type
    if field_type == "Decimal":
        data_type = type_mapping[field_type](scale, precision)
    else:
        data_type = type_mapping.get(field_type, StringType())  # Default to StringType if unknown

    # Create field schema
    struct_field = StructField(field_name, data_type, True)

    # Append schema fields to respective table
    if table_name not in table_schemas:
        table_schemas[table_name] = []
    table_schemas[table_name].append(struct_field)

# Convert list of fields to StructType for each table
for table in table_schemas:
    table_schemas[table] = StructType(table_schemas[table])

# Output: Dictionary of table schemas
# print(table_schemas)


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ##### **Flatten After  & Before Record**

# CELL ********************


# Infer schema dynamically from 'AfterRecord' column
json_schema = spark.read.json(extracted_dfrawdata.rdd.map(lambda row: row["AfterRecord"])).schema

# Parse 'AfterRecord' JSON and flatten structure
extracted_dfrawdata_flattenedAfter = (
    extracted_dfrawdata
    .filter(col("AfterRecord").isNotNull())  # Filter null records early
    .withColumn("AfterRecord_json", from_json(col("AfterRecord"), json_schema))
    .select("operation", "schema", "table", "time_stamp", "AfterRecord_json.*")
    .drop("_corrupt_record")  # Drop corrupt records column if exists
)

# Parse 'BeforeRecord' JSON and flatten structure for deleted records
extracted_dfrawdata_flattenedBefore = (
    extracted_dfrawdata
    .filter((col("BeforeRecord").isNotNull()) & (col("operation") == "d"))
    .withColumn("BeforeRecord_json", from_json(col("BeforeRecord"), json_schema))
    .select("operation", "schema", "table", "time_stamp", "BeforeRecord_json.*")
    .drop("_corrupt_record")
)

# Register temp views
extracted_dfrawdata_flattenedAfter.createOrReplaceTempView("vw_extractedrawdata_flattenedAfter")
extracted_dfrawdata_flattenedBefore.createOrReplaceTempView("vw_extractedrawdata_flattenedBefore")

# Combine Before & After DataFrames only if they are not empty
if extracted_dfrawdata_flattenedBefore.count() > 0 and extracted_dfrawdata_flattenedAfter.count() > 0:
    extracted_dfrawdata_flattened = extracted_dfrawdata_flattenedBefore.unionByName(extracted_dfrawdata_flattenedAfter, allowMissingColumns=True)
elif extracted_dfrawdata_flattenedBefore.count() > 0:
    extracted_dfrawdata_flattened = extracted_dfrawdata_flattenedBefore
elif extracted_dfrawdata_flattenedAfter.count() > 0:
    extracted_dfrawdata_flattened = extracted_dfrawdata_flattenedAfter
else:
    # Create an empty DataFrame with the same schema as BeforeRecord for consistency
    extracted_dfrawdata_flattened = spark.createDataFrame([], extracted_dfrawdata_flattenedBefore.schema)

# Register combined view
extracted_dfrawdata_flattened.createOrReplaceTempView("vw_extractedrawdata_flattened")

# # Define Delta Table Path
# delta_table_path = f"{landinglayertablepath}/rawSnapshotFlattened"

# # Append raw flattened data into Delta table with optimized write
# extracted_dfrawdata_flattened.write.format("delta") \
#     .option("mergeSchema", "true") \
#     .mode("append") \
#     .save(delta_table_path)


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ##### **CDC Code Changes for Schema Evolution**

# MARKDOWN ********************

# ##### **Perform CDC and Prepare Bronze Layer**

# CELL ********************

#------02-04-2025


#--------------------------------------- Load the metadata table containing primary keys
metadata_df = spark.read.format("delta").load(f"{masterlakehousetablepath}config_mastertablelist")

# ----------------------------------------Get distinct operations and tables
operationtabledf = spark.sql("""
    SELECT DISTINCT operation, table 
    FROM vw_extractedrawdata_flattened 
 -- WHERE table LIKE '%invgrp%'
""")

#-------------------------------------------------- Process each table
for row in operationtabledf.collect():
    table_name = row["table"]
    operation = row["operation"]
    
    try:
        if table_name:
            print(f"Processing table: {table_name}")

            # ---------------------------------------------Load the Delta table schema
            delta_path = f"{filepath}{table_name}"

            # ----------------------------------------------Get primary key
            primary_key_row = metadata_df.filter(col("TableName") == table_name).select("PrimaryKey").collect()
            if not primary_key_row:
                print(f"No primary key found for table: {table_name}. Skipping.")
                continue
            primary_key = primary_key_row[0]["PrimaryKey"]

            #------------------------------------------------ Load schema and data
            schema = table_schemas[table_name]

            #----------------------------------------------- Ensure it's a StructType before modifying
            if isinstance(schema, StructType):
                # Append the 'operation' field dynamically (if not already present)
                if "operation" not in [field.name for field in schema.fields]:
                    schema = StructType(schema.fields + [StructField("operation", StringType(), True)])

            
            # -------------------------------------------------Extract column types from schema
            timestamp_cols = [field.name for field in schema.fields if isinstance(field.dataType, TimestampType)]
            date_cols = [field.name for field in schema.fields if isinstance(field.dataType, DateType)]
            decimal_cols = [(field.name, field.dataType.precision, field.dataType.scale) for field in schema.fields if isinstance(field.dataType, DecimalType)]

            #----------------------------------------------------- Extract required column names
            required_columns = [field.name for field in schema.fields]
 
            raw_df = spark.sql(f"SELECT * FROM vw_extractedrawdata_flattened WHERE table = '{table_name}'")

            #------------------------------------------------------------ Select only required columns
            raw_df = raw_df.select(*[col(c) for c in required_columns if c in raw_df.columns])

            # print("---Raw  Data Schema Selected Columns---")
            # display(raw_df.printSchema())


            # ----------------------------------------------------------Convert timestamp columns
            for ts_col in timestamp_cols:
                if ts_col in raw_df.columns:
                    raw_df = raw_df.withColumn(ts_col, from_unixtime(col(ts_col) / 1000, "yyyy-MM-dd HH:mm:ss").cast("timestamp"))

            # ------------------------------------------------------------Convert date columns
            for date_col in date_cols:
                raw_df = raw_df.withColumn(date_col, col(date_col).cast("date"))

            #------------------------------------------------------------START------Apply decimal transformations-----------------------------------------

            # --------------------------------------------------------------------Check the data before decoding------------------------

            # print("-----CheckPoint 2--Check the data before decoding-------")
            # display(raw_df.select(*required_columns).limit(1))

            # Apply decimal transformations
            for num_col, precision, scale in decimal_cols:
                if num_col in raw_df.columns:
                    # print(f"Processing numeric column: {num_col} with Precision {precision} scale {scale}")
                    convert_udf = udf(lambda value: convert_pricefactor(value, scale), StringType())
                    raw_df = raw_df.withColumn(num_col, convert_udf(col(num_col)).cast(DecimalType(precision, scale)))

            # --------------------------------------------------------------------------Check the data after decoding----------------------------

            # print("----CheckPoint 3---Check the data after decoding----")
            # display(raw_df.select(*required_columns).limit(1))

            #-----------------------------------------------------------END------Apply decimal transformations-----------------------------------------


            #-----------------------------------START ----- CheckPoints----------------------
            # print("---Raw  Data---")
            # # display(raw_df.printSchema())

            # # Count the number of columns
            # column_count = len(raw_df.columns)
            # print(f"Total Raw df columns: {column_count}")

            # # print(table_schemas[table_name])

            
            #-----------------------------------END ----- CheckPoints----------------------


            # ------------------------------------------------------------------------Apply schema-------------------------------------------------------------

            flattened_df = spark.createDataFrame(raw_df.rdd, schema=schema)
            # flattened_df.cache()


            #-----------------------------------START ----- CheckPoints----------------------

            # print("--- Flatten Data ---")
            # # flattened_df.printSchema()  # This prints the schema

            # # Count the number of columns
            # column_count = len(flattened_df.columns)
            # print(f"Total Flatten df columns: {column_count}")

            # print(" Flatten  data After Apply Schema")
            # display(flattened_df.limit(1))
            
                      
            #-----------------------------------END ----- CheckPoints----------------------

            # ----------------------------------------------------------------Remove duplicates once before splitting the data-------------------------
            flattened_df = flattened_df.dropDuplicates([primary_key])

            # --------------------------------------Drop "operation" early to avoid keeping it in memory longer than needed------------------

            flattened_df = flattened_df.withColumn("deleteflag", when(col("operation") == "d", lit(1)).otherwise(lit(0))).drop("operation")

            #--------------------------------------- Add `ModificationDatetime` column in IST timezone--------------------------------

            current_ist_time = datetime.now(ist).strftime('%Y-%m-%d %H:%M:%S')
            flattened_df  = flattened_df.withColumn("ModificationDatetime", lit(current_ist_time).cast("timestamp"))


            # ---------------------------------START - code to test schema evolution before starting upsert operations

            # print("Schema Evolution Start")
            flattened_df.limit(0).write.format("delta") \
                .option("mergeSchema", "true") \
                .mode("append") \
                .save(delta_path)
            # print("Schema Evolution End")

            # --------------------------------------------------END - code to test schema evolution before starting upsert operations



            #-------------------------------------------UPSERT----------------------------------

            delta_table = DeltaTable.forPath(spark, delta_path)
            if not flattened_df.isEmpty():
                delta_table.alias("target").merge(
                    flattened_df.alias("source"),
                    f"target.{primary_key} = source.{primary_key}"
                ).whenMatchedUpdateAll().whenNotMatchedInsertAll().execute()

                #Checkpoint Upsert
                # display(flattened_df.limit(1))
                print(f"Upsert completed for table: {table_name}")


    except Exception as e:
        print(f"Error processing table {table_name}: {e}")

        # flattened_df.unpersist()


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
