# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "96a72669-9e55-4ced-ab59-934fc239ed52",
# META       "default_lakehouse_name": "OnBoardingLakehouse",
# META       "default_lakehouse_workspace_id": "10f72987-5056-4f76-80a2-bf50df0fdc12",
# META       "known_lakehouses": [
# META         {
# META           "id": "96a72669-9e55-4ced-ab59-934fc239ed52"
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
import sempy.fabric as fabric
from notebookutils import mssparkutils
from pyspark.sql.types import *
import time
from pyspark.sql.types import StructType, StructField, StringType, LongType, DecimalType, TimestampType,  DoubleType, IntegerType,DateType
from pyspark.sql.functions import max, min
from datetime import timedelta
from pyspark.sql.functions import col, max as spark_max, date_trunc

from pyspark.sql.functions import expr

# Configure logging
logging.basicConfig(level=logging.ERROR)

# Define IST timezone
ist = pytz.timezone('Asia/Kolkata')



# Sets the datetime rebase mode to "LEGACY" when writing Parquet files.
# This ensures that Spark uses the old Julian calendar for dates before 1582, 
# matching the behavior of earlier Spark versions. 
# Use this setting to avoid date shifts when migrating legacy data or working with historical timestamps.
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInWrite", "LEGACY")


start = time.time()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# 
# 
# ##### **Get Lakehouse & Workspace Details**


# CELL ********************


#Get Workspace Name
wid=fabric.get_notebook_workspace_id()
print(f"Workspace ID: {wid}")

workspaces=fabric.list_workspaces()
current_workspace=workspaces[workspaces.Id == wid]
workspace_name=current_workspace['Name'].iloc[-1]


# Get list of lakehouses
lakehouselist = notebookutils.lakehouse.list()

# Initialize variables
Bronze_lakehouse_id = None
Landing_lakehouse_id = None

# Loop through and find matching lakehouses
for lakehouse in lakehouselist:
    if "Bronze" in lakehouse.displayName:
        Bronze_lakehouse_id = lakehouse.id
        print(f"Bronze Lakehouse ID: {Bronze_lakehouse_id}")

    if "Landing" in lakehouse.displayName:
        Landing_lakehouse_id = lakehouse.id
        print(f"Landing Lakehouse ID: {Landing_lakehouse_id}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ##### **Define Variables**

# CELL ********************

#------------------------------------Path
filepath=f"abfss://{wid}@onelake.dfs.fabric.microsoft.com/{Bronze_lakehouse_id}/Tables/"


#------------------------------Landing-------------------
landinglayerpath = f"abfss://{wid}@onelake.dfs.fabric.microsoft.com/{Landing_lakehouse_id}/"
landinglayertablepath = f"{landinglayerpath}Tables/"

#-----------------------------Bronze-------------------------

bronzelayerpath = f"abfss://{wid}@onelake.dfs.fabric.microsoft.com/{Bronze_lakehouse_id}/"
bronzelayertablepath = f"{bronzelayerpath}Tables/"

#-----------------------------Master-------------
masterlakehousepath=f"abfss://MasterGinesys@onelake.dfs.fabric.microsoft.com/OnBoardingLakehouse.Lakehouse/"
masterlakehousetablepath = f"{masterlakehousepath}Tables/"


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ##### **Get Snapshot Ingestion Timestamp Range**

# CELL ********************


tablename = "raw" + "_" + workspace_name

#-------------------------------------------------Config-----------------------

# Define the config ingestion path 
config_ingestion_path = f"{landinglayertablepath}config_ingestion"

# Read the data
df_config = spark.read.format("delta").load(config_ingestion_path)
display(df_config)


#------------------------------------------------Snapshot--------------

# Define the config ingestion path 
snapshot_path = f"{landinglayertablepath}{tablename}"

# Read the data
dfsnapshot  = spark.read.format("delta").load(snapshot_path)



#-------------------------------------------- Get max (last) ingestion_datetime
min_time = df_config.select(max("MaxIngestionTimestamp")).collect()[0][0]

# ------------------------------------------Get min ingestion time, Set seconds to 59 and truncate microseconds

# min_time = min_time.replace(second=0,microsecond=0)

min_time = min_time - timedelta(seconds=1)
min_time = min_time.replace(microsecond=0)


# -----------------------------------------Get max -> min ingestion_datetime
max_time = dfsnapshot.select(max("ingestion_datetime")).collect()[0][0]


#--------------------------------------- Get max ingestion time, Set seconds to 59 and truncate microseconds

# max_time = max_time.replace(microsecond=0)
# -------------------------------------------- 
# max_time = max_time.replace(second=59, microsecond=0)
print("Before adding 1 second:", max_time)
# Assuming max_time is a datetime object
max_time = max_time + timedelta(seconds=1)  # Add 1 second to max_time
print("After adding 1 second:", max_time)

max_time = max_time.replace(microsecond=59)  # Remove microseconds from max_time
print("After setting microsecond to 0:", max_time)

# # --------------------------------- Testing ----------------------------
# Get Min and Max timestamps
# df_configMin = df_config.selectExpr("LastIngestionTimestamp AS MinTimestamp")

# df_configMax = df_config.selectExpr("DATEADD(minute, 10, LastIngestionTimestamp) AS MaxTimestamp")
# #df_configMax = df_config.selectExpr("DATEADD(hours, 15, LastIngestionTimestamp) AS MaxTimestamp")

# # df_configMin = df_config.selectExpr("DATEADD(Day, -7, LastIngestionTimestamp) AS MinTimestamp")

# min_time='2025-04-22 13:21:25'
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

tablename = "raw" + "_" + workspace_name

# Define the config ingestion path 
snapshot_path = f"{landinglayertablepath}{tablename}"

# Read the data
dfsnapshot  = spark.read.format("delta").load(snapshot_path)
# display(df_config)

# Filter 
dfsnapshot = dfsnapshot.filter(
    (col("ingestion_datetime") > min_time) &
    (col("ingestion_datetime") <= max_time)
)
# # Order by ingestion_datetime ascending
# dfsnapshot = dfsnapshot.orderBy(col("ingestion_datetime").asc())

# query = f"select * from LandingLayer.sc_cdcpoc_snapshot_kql where ingestion_datetime > '{min_time}' and ingestion_datetime <= '{max_time}'"
# dfsnapshot = spark.sql(query)
display(dfsnapshot.count())
# display(dfsnapshot)

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
        #decoded_number = int.from_bytes(decoded_bytes, byteorder='big')
        decoded_number = int.from_bytes(decoded_bytes, byteorder='big', signed=True)

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
    col("json_data.before").alias("BeforeRecord"),
    col("ingestion_datetime").alias("ingestion_datetime")
)



# display(parsed_dfrawdata)
extracted_dfrawdata.createOrReplaceTempView("vw_extractedrawdata")

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
    ).when(
        col("Description").like("%Date%"), # Added  on 2025-04-15
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
after_fields_new = after_fields.dropDuplicates()

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



# Extract the fields from the 'after_fields' DataFrame
fields =after_fields_new.select("TableName", "Name", "FieldType", "Scale", "Precision").collect() 
# after_fields.select("TableName", "Name", "FieldType", "Scale", "Precision").collect()

# display(fields)
# Map field types to PySpark data types
type_mapping = {
    "string": StringType(),
    "int64": LongType(),
    "long": LongType(),
    "Decimal": lambda scale, precision: DecimalType(precision, scale),
    "Timestamp": TimestampType(),
    "int32": IntegerType(),
    "double": DoubleType(),
    "Date":DateType()
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

# ##### **Helper Function to Cast Based on Schema**

# CELL ********************


def cast_columns_according_to_schema(df, schema):
    for field in schema.fields:
        name = field.name
        dtype = field.dataType

        if name in df.columns:
            if isinstance(dtype, DecimalType):
                df = df.withColumn(name, col(name).cast(f"decimal({dtype.precision}, {dtype.scale})"))
            elif isinstance(dtype, DoubleType):
                df = df.withColumn(name, col(name).cast("double"))
            elif isinstance(dtype, LongType):
                df = df.withColumn(name, col(name).cast("long"))
            elif isinstance(dtype, IntegerType):
                df = df.withColumn(name, col(name).cast("int"))
            elif isinstance(dtype, TimestampType):
                df = df.withColumn(name, col(name).cast("timestamp"))
            elif isinstance(dtype, StringType):
                df = df.withColumn(name, col(name).cast("string"))
            elif isinstance(dtype, DateType):
                df = df.withColumn(name, col(name).cast("date"))
    return df


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
    .select("ingestion_datetime","operation", "schema", "table", "time_stamp", "AfterRecord_json.*")
    .drop("_corrupt_record")  # Drop corrupt records column if exists
)

# Parse 'BeforeRecord' JSON and flatten structure for deleted records
extracted_dfrawdata_flattenedBefore = (
    extracted_dfrawdata
    .filter((col("BeforeRecord").isNotNull()) & (col("operation") == "d"))
    .withColumn("BeforeRecord_json", from_json(col("BeforeRecord"), json_schema))
    .select("ingestion_datetime","operation", "schema", "table", "time_stamp", "BeforeRecord_json.*")
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

# Order by ingestion_datetime ascending
extracted_dfrawdata_flattened = extracted_dfrawdata_flattened.orderBy(col("ingestion_datetime").asc())

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

#--------------------------------------- Load the metadata table containing primary keys
metadata_df = spark.read.format("delta").load(f"{masterlakehousetablepath}config_mastertablelist")

# ----------------------------------------Get distinct operations and tables
operationtabledf = spark.sql("""
    SELECT DISTINCT operation, table 
    FROM vw_extractedrawdata_flattened 
 --WHERE table like  '%psite_posbill'
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
            #print(primary_key)

            #------------------------------------------------ Load schema and data
            schema = table_schemas[table_name]
            # display(schema)
            #----------------------------------------------- Ensure it's a StructType before modifying
            if isinstance(schema, StructType):
                # Append the 'operation' field dynamically (if not already present)
                if "operation" not in [field.name for field in schema.fields]:
                    schema = StructType(schema.fields + [StructField("operation", StringType(), True)])

                if "ingestion_datetime" not in [field.name for field in schema.fields]:
                    schema = StructType(schema.fields + [StructField("ingestion_datetime", TimestampType(), True)])

     
            # -------------------------------------------------Extract column types from schema
            # timestamp_cols = [field.name for field in schema.fields if isinstance(field.dataType, TimestampType)]

            # Extract timestamp columns from the schema, excluding 'ingestion_datetime'
            timestamp_cols = [field.name for field in schema.fields 
                            if isinstance(field.dataType, TimestampType) and field.name != 'ingestion_datetime']

            date_cols = [field.name for field in schema.fields if isinstance(field.dataType, DateType)]
            # print(f"Date Fields {date_cols}")
            decimal_cols = [(field.name, field.dataType.precision, field.dataType.scale) for field in schema.fields if isinstance(field.dataType, DecimalType)]
   
            #----------------------------------------------------- Extract required column names
            required_columns = [field.name for field in schema.fields]
 
            raw_df = spark.sql(f"SELECT * FROM vw_extractedrawdata_flattened WHERE table = '{table_name}' Order by ingestion_datetime ASC ")

            #------------------------------------------------------------ Select only required columns
            raw_df = raw_df.select(*[col(c) for c in required_columns if c in raw_df.columns])

            #updated condtion on 14-04-2025 as getting issues in admsite,admcity,invarticle during upsert
            #if "code" in raw_df.columns:
            #    raw_df = raw_df.withColumn("code", col("code").cast("long"))
            # print("---Raw  Data Schema Selected Columns---")
            # display(raw_df.printSchema())
            

            # ----------------------------------------------------------Convert timestamp columns
            for ts_col in timestamp_cols:
                if ts_col in raw_df.columns:
                    raw_df = raw_df.withColumn(ts_col, from_unixtime(col(ts_col) / 1000, "yyyy-MM-dd HH:mm:ss").cast("timestamp"))

            # ------------------------------------------------------------Convert date columns
            for date_col in date_cols:
                # raw_df = raw_df.withColumn(date_col, col(date_col).cast("date"))
                raw_df = raw_df.withColumn(
                    date_col,
                    expr(f"date_add('1970-01-01', CAST({date_col} AS INT))").cast("date")
                )

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

            # print("Raw  Data after typecast")
            # display(raw_df)
            # --------------------------------------------------------------------------Check the data after decoding----------------------------

            # print("----CheckPoint 3---Check the data after decoding----")
            # display(raw_df.select(*required_columns).limit(1))

            #-----------------------------------------------------------END------Apply decimal transformations-----------------------------------------


            #-----------------------------------START ----- CheckPoints----------------------
            # print("---Raw  Data---")
            # display(raw_df.printSchema())

            # # Count the number of columns
            # column_count = len(raw_df.columns)
            # print(f"Total Raw df columns: {column_count}")

            # # print(table_schemas[table_name])

            
            #-----------------------------------END ----- CheckPoints----------------------


            # ------------------------------------------------------------------------Apply schema-------------------------------------------------------------

            # flattened_df = spark.createDataFrame(raw_df.rdd, schema=schema)
            flattened_df= cast_columns_according_to_schema(raw_df, schema)
            # print("-- Flatten df -----------")
            # display(flattened_df)

            #print("0")
            # flattened_df.cache()
            # display(flattened_df.printSchema())


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
            flattened_df = flattened_df.dropDuplicates() 
            # flattened_df = flattened_df.dropDuplicates([primary_key]) 

            # if "ingestion_datetime" in flattened_df.columns:
            #     print(f"Before deduplication: {flattened_df.count()} records")

            #     window_spec = Window.partitionBy(primary_key).orderBy(col("ingestion_datetime").desc())
            #     flattened_df = flattened_df.withColumn("rn", row_number().over(window_spec)) \
            #                             .filter(col("rn") == 1) \
            #                             .drop("rn")

            #     print(f"After deduplication (latest per {primary_key}): {flattened_df.count()} records")

            #     # Optional: Drop ingestion_datetime if you don't need it post-upsert
            #     flattened_df = flattened_df.drop("ingestion_datetime")


    
            # --------------------------------------Drop "operation" early to avoid keeping it in memory longer than needed------------------

            flattened_df = flattened_df.withColumn("deleteflag", when(col("operation") == "d", lit(1)).otherwise(lit(0))).drop("operation")

            #--------------------------------------- Add `ModifiedDatetime` column in IST timezone--------------------------------

            current_ist_time = datetime.now(ist).strftime('%Y-%m-%d %H:%M:%S')
            flattened_df  = flattened_df.withColumn("ModifiedDatetime", lit(current_ist_time).cast("timestamp"))

            flattened_df = flattened_df.orderBy("ingestion_datetime")


   
            # ---------------------------------START - code to test schema evolution before starting upsert operations
            # display(flattened_df)
            # flattened_df.printSchema()
 


            delta_table = DeltaTable.forPath(spark, delta_path)
            # display(delta_table)
            # delta_table.toDF().printSchema()


            print("Schema Evolution Start")
            flattened_df.limit(0).write.format("delta") \
                .option("mergeSchema", "true") \
                .mode("append") \
                .save(delta_path)
            print("Schema Evolution End")

            # --------------------------------------------------END - code to test schema evolution before starting upsert operations



            #-------------------------------------------UPSERT----------------------------------

            delta_table = DeltaTable.forPath(spark, delta_path)
            # display(delta_table)
            # delta_table.printSchema()

            if not flattened_df.isEmpty():
                print("Upsert  Started")
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

# MARKDOWN ********************

# ##### **Update config_ingestion**

# CELL ********************

# #-------------------------------------------------Config-----------------------

df_config_updated = df_config.withColumn("MaxIngestionTimestamp", lit(max_time))


# Show the resulting DataFrame
display(df_config_updated)

# Define the config ingestion path 
config_ingestion_path = f"{landinglayertablepath}config_ingestion"

# Write the initial checkpoint DataFrame as a Delta table
df_config_updated.write.format("delta") \
    .mode("overwrite") \
    .save(config_ingestion_path)

print(f"Config table Updated: {config_ingestion_path }")

    # .option("mergeSchema", "true") \

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

print("Took:", round((time.time() - start) / 60, 2), "minutes")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
