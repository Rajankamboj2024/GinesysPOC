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

# ##### **Import the required libraries**

# CELL ********************

from pyspark.sql.utils import AnalysisException
from pyspark.sql.functions import lit,current_timestamp, from_utc_timestamp
from pyspark.sql import SparkSession
from pyspark.sql.functions import col
from pyspark.sql.types import TimestampType
import pandas as pd
from datetime import datetime
import pytz
import sempy.fabric as fabric
from pyspark.sql.types import StructType, StructField, TimestampType
from pyspark.sql.functions import max, min
from datetime import timedelta
# Initialize Spark session
spark = SparkSession.builder.getOrCreate()
from pyspark.sql import functions as F

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ##### **Define Parameters**

# CELL ********************

try:
    customerworkspace
except NameError:
    customerworkspace ="ESTELE-TEST" # "HYPHEN-TEST" #"fabric-test"

# Optional: Ensure it's still set if it was None
if customerworkspace is None:
    customerworkspace = "ESTELE-TEST"  # "HYPHEN-TEST" 

# customerworkspace = ""
# databasename = ""

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ##### **Configurations**

# CELL ********************

#Get current Workspace Details
workspace_id=fabric.get_notebook_workspace_id()
print(workspace_id)

workspaces=fabric.list_workspaces()
current_workspace=workspaces[workspaces.Id == workspace_id]
workspace_name=current_workspace['Name'].iloc[-1]
print(workspace_name)

# Define paths
masterlakehousepath="abfss://"+workspace_name+"@onelake.dfs.fabric.microsoft.com/OnBoardingLakehouse.Lakehouse/"
masterlakehousetablepath = f"{masterlakehousepath}Tables/"

# Read onboard configuration
print(customerworkspace)
df_configOnboarding = spark.sql(f"SELECT * FROM OnBoardingLakehouse.config_onboarding WHERE CustomerName='{customerworkspace}'")

# Source connection
# from azure.identity import DefaultAzureCredential
# from azure.keyvault.secrets import SecretClient

# key_vault_name = "your-keyvault-name"
# secret_name = "your-secret-name"

# credential = DefaultAzureCredential()
# kv_uri = f"https://{key_vault_name}.vault.azure.net"

# client = SecretClient(vault_url=kv_uri, credential=credential)
# retrieved_secret = client.get_secret(secret_name)

# print(f"Secret Value: {retrieved_secret.value}")
source_url =  "jdbc:postgresql://psql-emr-dev-03.postgres.database.azure.com:5432/"+databasename+""
source_user = "gslpgadmin"
source_password = "qs$3?j@*>CA6!#Dy"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ##### **Dynamic Schema and Function Definitions**
# 
# This script dynamically extracts table schemas from a source PostgreSQL database and creates corresponding empty Delta tables in the Lakehouse. It adapts to schema changes and can handle both inclusion and exclusion lists for tables.
# 
# The process works as follows:
# 1. **Schema Extraction:** The script queries the `information_schema.tables` to get all table names in the specified schema.
# 2. **Dynamic Table Creation:** For each table, Spark reads the schema using JDBC, then writes an empty Delta table to the Lakehouse.
# 3. **Schema Evolution:** The script uses the `mergeSchema` option to accommodate future schema changes.
# 4. **Inclusion/Exclusion Logic:** You can choose whether to include only certain tables or exclude specific ones (e.g., log or temp tables).
# 


# CELL ********************

# ---------------------------------START --> Function to create Delta table in bronze layer in customer workspace------------------

def create_empty_delta_table(table_name,table_schema,delta_table_path):
    try:
        print(f"Processing table: {table_schema}.{table_name}")
        
        # Read schema from source table
        df = spark.read \
            .format("jdbc") \
            .option("url", source_url) \
            .option("dbtable", f"{table_schema}.{table_name}") \
            .option("user", source_user) \
            .option("password", source_password) \
            .load()
        # viewname = "vwProcess" + "_" + table_name
        # print(viewname)
        # df.createOrReplaceTempView(viewname)
        # query = f"SELECT * FROM {viewname}"
        # print(query)
        # dfReqFields = spark.sql(query)
        dfReqFields =df
        # Path to Lakehouse table
        bronze_layer_path = f"{delta_table_path}{table_name}"

        # Get current UTC time
        utc_now = datetime.utcnow()

        # Convert to IST
        ist = pytz.timezone('Asia/Kolkata')
        ist_time = utc_now.astimezone(ist)

        # Format without timezone
        modifieddatetime = ist_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]  # Removes microseconds after 3 decimal places

        # Add deleteflag column (default 0 for active records)
        dfReqFields = dfReqFields.withColumn("deleteflag", lit(0).cast("int"))
 
        dfReqFields  = dfReqFields.withColumn("ModifiedDatetime", lit(modifieddatetime).cast("timestamp"))
        # dfReqFields = dfReqFields.withColumn("ModifiedDatetime", modifieddatetime)

        # display(dfReqFields)

        
        # Create empty Delta table with schema evolution
        dfReqFields.limit(0).write \
            .format("delta") \
            .mode("overwrite") \
            .option("mergeSchema", "true") \
            .save(bronze_layer_path)

        print(f"Empty Delta table '{table_name}' created successfully in Lakehouse!")

    except AnalysisException as e:
        print(f"Schema error for table {table_name}: {str(e)}")
    except Exception as e:
        print(f"Error processing table {table_name}: {str(e)}")
# ---------------------------------END --> Function to create Delta table in bronze layer in customer workspace------------------
# ---------------------------------END --> Function to create Delta table in bronze layer in customer workspace------------------

# # -----------------------START --> Function to create data type conversions config table in master workspace------------------------------
# def create_conversions_delta_table(table_name,table_schema):
#     try:
#         table_name = "'"+table_name+"'"
#         table_schema = "'"+table_schema+"'"
#         query=f"""SELECT 
#             t.table_catalog,
#             t.table_schema,
#             t.table_name,
#             c.column_name AS primary_key_column,
#             col.column_name AS numeric_column,
#             col.data_type,
#             col.numeric_precision,
#             col.numeric_scale
#         FROM INFORMATION_SCHEMA.TABLES t
#         LEFT JOIN INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc 
#             ON t.table_name = tc.table_name 
#             AND t.table_schema = tc.table_schema 
#             AND tc.constraint_type = 'PRIMARY KEY'
#         LEFT JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE c 
#             ON tc.constraint_name = c.constraint_name
#             AND tc.table_name = c.table_name
#             AND tc.table_schema = c.table_schema
#         LEFT JOIN INFORMATION_SCHEMA.COLUMNS col 
#             ON t.table_name = col.table_name 
#             AND t.table_schema = col.table_schema
#             AND col.data_type = 'numeric' -- or col.data_type   like '%time%'
#         WHERE t.table_schema = {table_schema}
#         AND t.table_name = {table_name}
#         ORDER BY t.table_schema, t.table_name
#         """

#         # Read the primary key information from the database
#         pk_df = spark.read \
#             .format("jdbc") \
#             .option("url", source_url) \
#             .option("dbtable", f"({query}) as meta_info") \
#             .option("user", source_user) \
#             .option("password", source_password) \
#             .load()

#         # Filter for the required tables
#         # pk_df = pk_df.filter(pk_df.table_name.isin(table_name))

#         # Show the results
#         # display(pk_df)

#         delta_table_conversions='config_conversions'
#         # Path to Lakehouse table
#         conv_lakehouse_path = f"{masterlakehousetablepath}{delta_table_conversions}"
#         print(conv_lakehouse_path)

#         # Save
#         pk_df.write \
#             .format("delta") \
#             .mode("append") \
#             .option("mergeSchema", "true") \
#             .save(conv_lakehouse_path)

#     except AnalysisException as e:
#         print(f"Schema error for table {table_name}: {str(e)}")
#     except Exception as e:
#         print(f"Error processing table {table_name}: {str(e)}")
# # -----------------------END --> Function to create data type conversions config table in master workspace------------------------------

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ##### **Prepare Bronze Layer**


# CELL ********************

for row in df_configOnboarding.collect():
    workspace_name = row['CustomerName']
    cust_workspace_id = row['WorkspaceId']

    delta_table_path = "abfss://" + workspace_name + "@onelake.dfs.fabric.microsoft.com/BronzeLayer.Lakehouse/Tables/"
 
    print(delta_table_path)

    #--------------------------Fetch required Tables -------------------------------------------
    df_configMetadata = spark.sql("SELECT TableSchema,TableName FROM OnBoardingLakehouse.config_mastertablelist")
    #table_names = [row['TableName'] for row in df_configMetadata.collect()]
    display(df_configMetadata)

    # ----- Call function to create empty delta tables in bronze layer
    # for table in table_names:
    for row in df_configMetadata.collect():
        table_name = row['TableName']
        table_schema = row['TableSchema']
        create_empty_delta_table(table_name,table_schema,delta_table_path)
    
    # ----- Call function to create data type conversions config table
    #for table in table_names:
        # create_conversions_delta_table(table_name,table_schema)

    print("All tables processed!")

    

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ##### **DimDate**


# CELL ********************

for row in df_configOnboarding.collect():
    workspace_name = row['CustomerName']
    cust_workspace_id = row['WorkspaceId']
    
    # Set start date and end date
    start_date = '2000-01-01'

    # Get today's date and find end of the current year
    today = F.current_date()
    end_of_year = F.last_day(F.add_months(today, 12 - F.month(today)))

    # Get start_date and end_date values
    dates_df = spark.sql(f"""
        SELECT to_date('{start_date}') AS StartDate,
            last_day(add_months(current_date(), 12 - month(current_date()))) AS EndDate
    """)

    # Collect dates
    start_date_val = dates_df.collect()[0]['StartDate']
    end_date_val = dates_df.collect()[0]['EndDate']

    print(f"Start Date: {start_date_val}")
    print(f"End Date: {end_date_val}")

    # Create a date range
    date_range = spark.sql(f"""
        SELECT explode(sequence(to_date('{start_date_val}'), to_date('{end_date_val}'), interval 1 day)) AS Date
    """)

    # Add columns
    date_table = date_range.withColumn("Year", F.year("Date")) \
        .withColumn("Month", F.month("Date")) \
        .withColumn("Day", F.dayofmonth("Date")) \
        .withColumn("Quarter", F.quarter("Date")) \
        .withColumn("MonthName", F.date_format("Date", "MMMM")) \
        .withColumn("DayofWeek", F.dayofweek("Date")) \
        .withColumn("WeekdayName", F.date_format("Date", "EEEE")) \
        .withColumn("MonthYear", 
            F.concat(F.date_format("Date", "MMM"), F.lit(" "), F.date_format("Date", "yy"))
        ) \
        .withColumn("MonthYearInt", 
            F.concat(F.date_format("Date", "yyyy"), F.date_format("Date", "MM")).cast("int")
        )


    delta_table_path = "abfss://" + workspace_name + "@onelake.dfs.fabric.microsoft.com/BronzeLayer.Lakehouse/Tables/DimDate"

    # Save as delta table
    date_table.write.mode("overwrite").format("delta").save(delta_table_path)

    # Display
    display(date_table.limit(1))


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ##### **Config Ingestion Time - (Moved to Manual Script)**

# CELL ********************

# for row in df_configOnboarding.collect():
#     workspacename = row['CustomerName']

#     # Get the current timestamp
#     min_time_firstsnapshot_df = spark.sql("SELECT from_utc_timestamp(current_timestamp(), 'Asia/Kolkata') as current_time")
#     min_time_firstsnapshot = min_time_firstsnapshot_df.collect()[0]["current_time"]
#     min_time_firstsnapshot = min_time_firstsnapshot.replace(microsecond=0)

#     # Define the schema
#     schema = StructType([
#         StructField("MinIngestionTimestamp", TimestampType(), True),
#        StructField("MaxIngestionTimestamp", TimestampType(), True)
#     ])

 
#     #------------------------------------------------Snapshot--------------
#     tablename = "raw" + "_" + workspacename
#     landinglayerpath = f"abfss://{workspacename}@onelake.dfs.fabric.microsoft.com/LandingLayer.Lakehouse/"
#     landinglayertablepath = f"{landinglayerpath}Tables/"

#     # Define the config ingestion path 
#     snapshot_path = f"{landinglayertablepath}{tablename}"

#     # Read the data
#     dfsnapshot  = spark.read.format("delta").load(snapshot_path)


#     # -----------------------------------------Get max , min ingestion_datetime
#     #     # Convert ingestion_datetime to IST and get the minimum value
#     # min_time_firstsnapshot = dfsnapshot \
#     #     .select(from_utc_timestamp(min("ingestion_datetime"), "Asia/Kolkata").alias("min_ist")) \
#     #     .collect()[0]["min_ist"]

#     # # Subtract 1 hour and remove microseconds
#     # min_time_firstsnapshot = (min_time_firstsnapshot - timedelta(hours=1)).replace(microsecond=0)

  
#     min_time_firstsnapshot =dfsnapshot.select(min("ingestion_datetime")).collect()[0][0]
#     # Subtract 1 hour from the timestamp
#     min_time_firstsnapshot = (min_time_firstsnapshot - timedelta(hours=1)).replace(microsecond=0)



#     # Create a DataFrame with the current timestamp
#     df = spark.createDataFrame([(min_time_firstsnapshot, min_time_firstsnapshot)], schema)


#     # Show the resulting DataFrame
#     display(df)

#     delta_table_path = "abfss://" + workspacename + "@onelake.dfs.fabric.microsoft.com/LandingLayer.Lakehouse/Tables/"
#     print(delta_table_path)
#     # Define the Delta path
#     path = f"{delta_table_path}config_ingestion"

#     # Write the initial checkpoint DataFrame as a Delta table
#     df.write.format("delta") \
#         .option("mergeSchema", "true") \
#         .mode("overwrite") \
#         .save(path)

#     print(f"Config table successfully written to: {path}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# # --------------------------------------------------
# # Currently Suspended - Code Cell 14-19
# # --------------------------------------------------


# MARKDOWN ********************

# ##### **Generate access token for Fabric REST API**

# CELL ********************

# # --------------------------------------------------
# # Currently Suspended this approach
# # --------------------------------------------------


# # ---------------will use Azure Key vault
# import requests

tenant_id = ""
client_id =  ""
client_secret = ""
# auth_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"

# auth_data = {
#     'grant_type': 'client_credentials',
#     'client_id': client_id,
#     'client_secret': client_secret,
#     'scope': 'https://api.fabric.microsoft.com/.default'
    
# }

# response = requests.post(auth_url, data=auth_data)

# access_token= response.json().get("access_token")
# if response.status_code == 200:
#     print("Access token generated") #, response.json().get("access_token"))
# else:
#     print(f"Failed to get token: {response.status_code} - {response.text}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ##### **Copy CDC Notebook to Customer Workspace**

# CELL ********************

# --------------------------------------------------
# Currently Suspended this approach
# --------------------------------------------------

# for row in df_configOnboarding.collect():
#     workspace_name = row['CustomerName']
#     cust_workspace_id = row['WorkspaceId']

#     # Headers
#     headers = {
#         "Authorization": f"Bearer {access_token}",
#         "Content-Type": "application/json"
#     }

#     # Source workspace and notebook
#     source_workspace_id = workspace_id
#     source_notebook_name = "CDC_Processing_Final_v1"

#     # Export the notebook
#     url_notebooks = f"https://api.fabric.microsoft.com/v1/workspaces/{source_workspace_id}/notebooks"

#     response = requests.get(url_notebooks, headers=headers)
#     notebook_content = response.json()

#     # Destination workspace
#     destination_workspace_id = cust_workspace_id
#     import_url = f"https://api.fabric.microsoft.com/v1/workspaces/{destination_workspace_id}/notebooks/"

#     # Import the notebook into destination workspace
#     payload = {
#         "displayName": source_notebook_name
#         # "notebookContent": notebook_content["notebookContent"]
#     }

#     import_response = requests.post(import_url, headers=headers, json=payload)

#     if import_response.status_code == 201:
#         print("Notebook copied successfully.")
#     else:
#         print("Error:", import_response.text)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ##### **Copy Delete script Notebook to Customer Workspace**

# CELL ********************

# --------------------------------------------------
# Currently Suspended this approach
# --------------------------------------------------

# # Headers
# headers = {
#     "Authorization": f"Bearer {access_token}",
#     "Content-Type": "application/json"
# }

# # Source workspace and notebook
# source_workspace_id = workspace_id
# source_notebook_name = "Deletion_Script"

# # Export the notebook
# url_notebooks = f"https://api.fabric.microsoft.com/v1/workspaces/{source_workspace_id}/notebooks"

# response = requests.get(url_notebooks, headers=headers)
# notebook_content = response.json()

# # Destination workspace
# destination_workspace_id = cust_workspace_id
# import_url = f"https://api.fabric.microsoft.com/v1/workspaces/{destination_workspace_id}/notebooks/"

# # Import the notebook into destination workspace
# payload = {
#     "displayName": source_notebook_name
# }

# import_response = requests.post(import_url, headers=headers, json=payload)

# if import_response.status_code == 201:
#     print("Notebook copied successfully.")
# else:
#     print("Error:", import_response.text)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
