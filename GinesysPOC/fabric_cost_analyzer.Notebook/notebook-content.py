# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "3c42cbd7-13ba-470b-b652-04a5ed96e475",
# META       "default_lakehouse_name": "BronzeLayer",
# META       "default_lakehouse_workspace_id": "c5672fc9-2a13-4083-9a9e-caa93efa804f",
# META       "known_lakehouses": [
# META         {
# META           "id": "3c42cbd7-13ba-470b-b652-04a5ed96e475"
# META         },
# META         {
# META           "id": "dd94153f-eefc-40df-a6ce-1a20b37ea3dc"
# META         }
# META       ]
# META     },
# META     "environment": {}
# META   }
# META }

# MARKDOWN ********************

# #### Fabric POC Cost Analyzer v0.2
# ###### This Cost Analyzer notebook will allow you to track the true cost per query of a Fabric Warehouse or Lakehouse Query based on the amount of Capacity Units (CUs) consumed and will help you estimate the capacity size you will need to run these queries. 
# ###### Due to the ability of Fabric Warehouse and Lakhouse SQL Endpoints to [burst up to 12X the workspace capacity](https://learn.microsoft.com/en-us/fabric/data-warehouse/burstable-capacity#sku-guardrails) it is important to understand this behavior on a per query basis to choose the appropriate [Fabric Capacity F SKU](https://azure.microsoft.com/en-us/pricing/details/microsoft-fabric/) that you can use to calculate your Fabric TCO. 
# 
# ###### This notebook accomplishes this by using [Semantic Link](https://learn.microsoft.com/en-us/fabric/data-science/semantic-link-overview) to query data from the [Capacity Metrics App](https://learn.microsoft.com/en-us/fabric/enterprise/metrics-app) and correlates it to query information from [Query Insights](https://learn.microsoft.com/en-us/fabric/data-warehouse/query-insights). However, due to Capacity Metrics information only being available via DAX queries against the semantic model, this approach may take up to 3-4+ hours to run. Logging has been added to estimate how long the notebook will take to run.


# MARKDOWN ********************

# ###### **Pre-Requisites**
# ###### 1. [Install the Capacity Metrics App](https://learn.microsoft.com/en-us/fabric/enterprise/metrics-app-install?tabs=1st).
# ###### 2. Capacity Admin should get the capacity ID used for this workspace from the Admin Portal.
# ###### 3. Create and attach a Fabric Spark environment that includes the `semantic-link` pypi library.
# ###### 4. Create and attach a Lakehouse to this notebook.
# ###### 5. All Warehouse and Lakehouse Query runs need to be done on Lakehouses or Warehouses in this workspace. If not, you need to create shortcuts to those tables in other workspaces within the Lakehouse attached to this notebook.
# ###### 6. Replace the parameters in cell 4 with the appropriate values.

# CELL ********************

# Import Libraries
from datetime import datetime, timedelta
from sempy.fabric import evaluate_dax
import warnings
from pyspark.sql.utils import AnalysisException
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, TimestampType
from tqdm import tqdm
import time
import pandas as pd
from sempy import fabric

# Suppress specific UserWarnings
warnings.filterwarnings("ignore", category=UserWarning, message="Ambiguous column name")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# PARAMETERS CELL ********************

# Capacity Metrics App Semantic Model Name - 'Fabric Capacity Metrics' is the default name
dataset = '<>' 

# Capacity Id - capacity admin can find this in Admin Portal
capacity_id = '<>' 

# Get workspace name
workspace_name = fabric.resolve_workspace_name(fabric.get_workspace_id())

# Integer or Decimal number of days to look at. Can set to "all" to include all usage data
number_of_days = "<>"

# Optional parameter to reduce the number of timepoints searched for testing. Set to "no" to include all timepoints. Start with a smaller number to test.
limit_num_timepoints = "<>"

# Optional parameter to filter to a list of Fabric data items to collect usage from. Set to "no" to include all data items.
limit_data_items = ['<>']

# Adjust based on the CU regional pricing for your capacity
regional_pricing_per_cu = #

# Name of the lakehouse you created and attached to this workspace
cost_analyzer_lakehouse = '<>'

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Define the schema for the DataFrame
dataframe_schema = StructType([
    StructField("OperationID", StringType(), True),
    StructField("Status", StringType(), True),
    StructField("User", StringType(), True),
    StructField("Operation", StringType(), True),
    StructField("WorkspaceName", StringType(), True),
    StructField("Item", StringType(), True),
    StructField("ItemName", StringType(), True),
    StructField("DurationSec", DoubleType(), True),
    StructField("TotalCUSec", DoubleType(), True),
    StructField("CapacityCU", DoubleType(), True),
    StructField("capacityId", StringType(), True),
    StructField("OperationType", StringType(), True)
])

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Refresh semantic model to ensure latest data is available
# fabric.refresh_dataset(dataset = dataset, refresh_type = "full")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ###### Check if the semantic model was refreshed. Continue after it is refreshed.

# CELL ********************

def format_time(seconds):
    """
    Function to format the time in a human-readable format.
    """
    if seconds < 60:
        return f"{seconds:.2f} seconds"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.2f} minutes"
    else:
        hours = seconds / 3600
        return f"{hours:.2f} hours"

def get_dax_query_filtered_timepoints():
    dax_query_filtered_timepoints = """
    EVALUATE
    FILTER (
        VALUES('TimePoints'[TimePoint]),
        CALCULATE([Cumulative CU Usage (s)]) > 0
    )
    """
    return dax_query_filtered_timepoints

def insert_or_append(df, table_name):
    """
    Function to insert or append the DataFrame into the specified Delta table.
    """
    df.write.format("delta").mode("append").saveAsTable(table_name)

def fetch_and_process_dax(timepoint, capacity_id, limit_data_items):
    timepoint_str = timepoint.strftime("%Y-%m-%d %H:%M:%S")
    timepoint_dt = datetime.strptime(timepoint_str, "%Y-%m-%d %H:%M:%S")
    current_year = str(timepoint_dt.year)
    current_month = str(timepoint_dt.month)
    current_day = str(timepoint_dt.day)
    starting_hour = str(timepoint_dt.hour)
    starting_minutes = str(timepoint_dt.minute)
    starting_seconds = str(timepoint_dt.second)

    dax_background_operation = f'''
        DEFINE
            MPARAMETER 'CapacityID' = "{capacity_id}"
            MPARAMETER 'TimePoint' = (DATE({current_year}, {current_month}, {current_day}) + TIME({starting_hour}, {starting_minutes}, {starting_seconds}))
            VAR varFilter_Capacity = TREATAS({{"{capacity_id}"}}, 'Capacities'[capacityId])
            VAR varFilter_TimePoint = 
                TREATAS(
                    {{(DATE({current_year}, {current_month}, {current_day}) + TIME({starting_hour}, {starting_minutes}, {starting_seconds}))}},
                    'TimePoints'[TimePoint]
                )
            VAR varTable_Details =
                SUMMARIZECOLUMNS(
                    'TimePointBackgroundDetail'[OperationId],
                    'TimePointBackgroundDetail'[Status],
                    'TimePointBackgroundDetail'[User],
                    'TimePointBackgroundDetail'[Operation],
                    'Items'[WorkspaceName],
                    'Items'[ItemKind],
                    'Items'[ItemName],
                    'TimePointBackgroundDetail'[Capacity CU (s)],
                    varFilter_Capacity,
                    varFilter_TimePoint,
                    "DurationSec", SUM('TimePointBackgroundDetail'[Duration (s)]),
                    "TotalCUSec", CALCULATE(SUM('TimePointBackgroundDetail'[Total CU (s)]))
                )
        EVALUATE  SELECTCOLUMNS(
            varTable_Details,
            "OperationID", [OperationId],
            "Status", [Status],
            "User", [User],
            "Operation", [Operation],
            "WorkspaceName", [WorkspaceName],
            "Item", [ItemKind],
            "ItemName", [ItemName],
            "DurationSec", [DurationSec],
            "TotalCUSec", [TotalCUSec],
            "CapacityCU", [Capacity CU (s)] / 30
        )'''

    # Evaluate the DAX query and get the result
    df_dax_result = evaluate_dax(dataset, dax_background_operation)

    # Rename columns to remove brackets
    df_dax_result.columns = [col.strip('[]') for col in df_dax_result.columns]

    # Add capacityId and OperationType columns, and remove duplicates based on OperationID
    if not df_dax_result.empty:
        df_dax_result['capacityId'] = capacity_id
        df_dax_result['OperationType'] = 'background'
        df_dax_result = df_dax_result.drop_duplicates(subset=['OperationID'])
        return df_dax_result
    else:
        return pd.DataFrame()

def generate_dax_background_operation(filtered_timepoints, capacity_id, limit_num_timepoints="no", limit_data_items="no"):
    if not filtered_timepoints:
        print("No timepoints to process.")
        return

    if limit_num_timepoints != "no":
        limit_num_timepoints = int(limit_num_timepoints)
        filtered_timepoints = filtered_timepoints[:limit_num_timepoints]

    if not filtered_timepoints:
        print("No timepoints to process after applying the limit.")
        return

    total_timepoints = len(filtered_timepoints)
    start_time = time.time()
    
    results = []
    estimated_time_per_timepoint = 0
    progress_bar = tqdm(filtered_timepoints, desc="Processing Timepoints", unit="timepoint", mininterval=1, dynamic_ncols=True)

    for i, timepoint in enumerate(progress_bar):
        df_dax_result = fetch_and_process_dax(timepoint, capacity_id, limit_data_items)
        
        if not df_dax_result.empty:
            results.append(df_dax_result)
        else:
            print(f"No data extracted for timepoint {timepoint}")
        
        elapsed_time = time.time() - start_time
        estimated_time_per_timepoint = elapsed_time / (i + 1)
        remaining_time = estimated_time_per_timepoint * (total_timepoints - (i + 1))
        remaining_time_formatted = format_time(remaining_time)
        
        progress_bar.set_postfix_str(f"Est. remaining time: {remaining_time_formatted}")

    if results:
        combined_df = pd.concat(results, ignore_index=True)
        
        numeric_columns = [
            "DurationSec", "TotalCUSec", "CapacityCU"
        ]

        for col in numeric_columns:
            combined_df[col] = combined_df[col].astype(float)
        
        combined_df = combined_df.drop_duplicates(subset=['OperationID'])

        spark.conf.set("spark.sql.execution.arrow.pyspark.enabled", "false")
        combined_df_spark = spark.createDataFrame(combined_df, schema=dataframe_schema)
        spark.conf.set("spark.sql.execution.arrow.pyspark.enabled", "true")

        insert_or_append(combined_df_spark, "bronze_all_background_operations")
        print(f"Inserted {len(combined_df)} rows into bronze_all_background_operations")
    else:
        print("No data to insert into bronze_all_background_operations")

    elapsed_time = time.time() - start_time
    elapsed_time_formatted = format_time(elapsed_time)
    print(f'Progress: Complete, Total time: {elapsed_time_formatted}')

def filter_and_save_operations(limit_data_items, workspace_name):
    df_bronze = spark.table("bronze_all_background_operations")

    if limit_data_items != "no":
        df_bronze = df_bronze.filter(df_bronze["ItemName"].isin(limit_data_items))
    df_bronze = df_bronze.filter(df_bronze["Operation"].isin(["Warehouse Query", "SQL Endpoint Query"]))
    df_bronze = df_bronze.filter(df_bronze["WorkspaceName"] == workspace_name)
    df_bronze = df_bronze.filter(df_bronze["User"] != "System")

    insert_or_append(df_bronze, "silver_dw_lh_queries")
    print(f"Inserted {df_bronze.count()} rows into silver_dw_lh_queries")

def ensure_table_exists(table_name, schema):
    """
    Function to ensure that a table exists. If it doesn't, create an empty table with the given schema.
    """
    try:
        spark.table(table_name)
    except AnalysisException:
        print(f"Table '{table_name}' does not exist, creating now...")
        empty_df = spark.createDataFrame([], schema)
        empty_df.write.format("delta").saveAsTable(table_name)

def ensure_tables_exist():
    """
    Function to ensure that the necessary tables exist.
    """
    ensure_table_exists("bronze_all_background_operations", dataframe_schema)
    ensure_table_exists("silver_dw_lh_queries", dataframe_schema)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Ensure the necessary tables exist
ensure_tables_exist()

# Get the DAX query for filtered timepoints
dax_query_filtered_timepoints = get_dax_query_filtered_timepoints()

# Evaluate the DAX query and get the filtered timepoints
df_filtered_timepoints = evaluate_dax(dataset, dax_query_filtered_timepoints)

# Extract the filtered timepoints from the query result
if 'TimePoints[TimePoint]' in df_filtered_timepoints.columns:
    filtered_timepoints = df_filtered_timepoints['TimePoints[TimePoint]'].tolist()
else:
    print("Column 'TimePoints[TimePoint]' not found. Please check the DataFrame.")
    filtered_timepoints = df_filtered_timepoints.iloc[:, 0].tolist()

# Calculate the cutoff date if number_of_days is not "all"
if number_of_days != "all":
    cutoff_date = datetime.now() - timedelta(days=number_of_days)
    filtered_timepoints = [tp for tp in filtered_timepoints if tp >= cutoff_date]
else:
    cutoff_date = None

print(f"Cutoff date: {cutoff_date}")

# Run the function with the updated parameters
generate_dax_background_operation(filtered_timepoints, capacity_id, limit_num_timepoints, limit_data_items)

# Filter and save operations
filter_and_save_operations(limit_data_items, workspace_name)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ###### Check the top rows of the bronze and silver tables to validate that records were written

# CELL ********************

display(spark.sql(f"SELECT * FROM {cost_analyzer_lakehouse}.bronze_all_background_operations LIMIT 5"))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

display(spark.sql(f"SELECT * FROM {cost_analyzer_lakehouse}.silver_dw_lh_queries LIMIT 5"))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Read the background_operations table
queries_df = spark.sql(f"SELECT DISTINCT WorkspaceName, Item, ItemName FROM {cost_analyzer_lakehouse}.silver_dw_lh_queries")

# Collect unique values from the DataFrame
unique_items = queries_df.collect()

# Construct the T-SQL query to union all query insights and join with background operations
query_parts = []
for row in unique_items:
    item_name = row['ItemName']
    
    # Calculate the recommended capacity in CU
    rec_capacity_cu = f"""
    CASE
        WHEN b.TotalCUSec / NULLIF(b.DurationSec, 0) <= 2 THEN 'F2'
        WHEN b.TotalCUSec / NULLIF(b.DurationSec, 0) <= 4 THEN 'F4'
        WHEN b.TotalCUSec / NULLIF(b.DurationSec, 0) <= 8 THEN 'F8'
        WHEN b.TotalCUSec / NULLIF(b.DurationSec, 0) <= 16 THEN 'F16'
        WHEN b.TotalCUSec / NULLIF(b.DurationSec, 0) <= 32 THEN 'F32'
        WHEN b.TotalCUSec / NULLIF(b.DurationSec, 0) <= 64 THEN 'F64'
        WHEN b.TotalCUSec / NULLIF(b.DurationSec, 0) <= 128 THEN 'F128'
        WHEN b.TotalCUSec / NULLIF(b.DurationSec, 0) <= 256 THEN 'F256'
        WHEN b.TotalCUSec / NULLIF(b.DurationSec, 0) <= 512 THEN 'F512'
        WHEN b.TotalCUSec / NULLIF(b.DurationSec, 0) <= 1024 THEN 'F1024'
        WHEN b.TotalCUSec / NULLIF(b.DurationSec, 0) <= 2048 THEN 'F2048'
        ELSE 'Above F2048'
    END"""

    # Construct the query part for each unique item
    query_part = f"""
SELECT
    '{item_name}' AS DataItem,
    a.distributed_statement_id,
    a.login_name,
    a.command,
    a.start_time,
    a.end_time,
    ROUND(b.DurationSec, 2) AS DurationSec,
    ROUND(b.DurationSec / 3600, 5) AS DurationHr,
    ROUND(b.TotalCUSec, 2) AS TotalCUs,
    b.CapacityCU AS ExpectedCUsPerSec,
    ROUND(b.TotalCUSec / NULLIF(b.DurationSec, 0), 2) AS ActualCUsPerSec,
    CASE
        WHEN b.TotalCUSec / NULLIF(b.DurationSec, 0) > b.CapacityCU THEN 'Yes'
        ELSE 'No'
    END AS IsBursting,
    ROUND(
        CASE
            WHEN b.TotalCUSec / NULLIF(b.DurationSec, 0) > b.CapacityCU THEN b.TotalCUSec / NULLIF(b.DurationSec, 0) / b.CapacityCU
            ELSE b.TotalCUSec / NULLIF(b.DurationSec, 0) / b.CapacityCU
        END, 2) AS BurstingMultiplier,
    {regional_pricing_per_cu} AS RegionalCUPerHourCost,
    {regional_pricing_per_cu} * ROUND(b.DurationSec / 3600, 5) * b.CapacityCU AS ExpectedCostQuery,
    {regional_pricing_per_cu} * ROUND(b.DurationSec / 3600, 5) * ROUND(b.TotalCUSec / NULLIF(b.DurationSec, 0), 2) AS ActualCostQuery,
    CASE
        WHEN b.CapacityCU <= 2 THEN 'F2'
        WHEN b.CapacityCU <= 4 THEN 'F4'
        WHEN b.CapacityCU <= 8 THEN 'F8'
        WHEN b.CapacityCU <= 16 THEN 'F16'
        WHEN b.CapacityCU <= 32 THEN 'F32'
        WHEN b.CapacityCU <= 64 THEN 'F64'
        WHEN b.CapacityCU <= 128 THEN 'F128'
        WHEN b.CapacityCU <= 256 THEN 'F256'
        WHEN b.CapacityCU <= 512 THEN 'F512'
        WHEN b.CapacityCU <= 1024 THEN 'F1024'
        WHEN b.CapacityCU <= 2048 THEN 'F2048'
        ELSE 'Above F2048'
    END AS CapacityUsed,
    {rec_capacity_cu} AS CapacityRec,
    CAST(ROUND(b.CapacityCU * {regional_pricing_per_cu} * 24 * 30, 0) AS INT) AS CapacityUsedMonthlyCost,
    CAST(ROUND(b.CapacityCU * {regional_pricing_per_cu} * 24 * 365, 0) AS INT) AS CapacityUsedYearlyCost,
    CAST(ROUND((CASE
        WHEN b.TotalCUSec / NULLIF(b.DurationSec, 0) <= 2 THEN 2
        WHEN b.TotalCUSec / NULLIF(b.DurationSec, 0) <= 4 THEN 4
        WHEN b.TotalCUSec / NULLIF(b.DurationSec, 0) <= 8 THEN 8
        WHEN b.TotalCUSec / NULLIF(b.DurationSec, 0) <= 16 THEN 16
        WHEN b.TotalCUSec / NULLIF(b.DurationSec, 0) <= 32 THEN 32
        WHEN b.TotalCUSec / NULLIF(b.DurationSec, 0) <= 64 THEN 64
        WHEN b.TotalCUSec / NULLIF(b.DurationSec, 0) <= 128 THEN 128
        WHEN b.TotalCUSec / NULLIF(b.DurationSec, 0) <= 256 THEN 256
        WHEN b.TotalCUSec / NULLIF(b.DurationSec, 0) <= 512 THEN 512
        WHEN b.TotalCUSec / NULLIF(b.DurationSec, 0) <= 1024 THEN 1024
        WHEN b.TotalCUSec / NULLIF(b.DurationSec, 0) <= 2048 THEN 2048
        ELSE 0
    END) * {regional_pricing_per_cu} * 24 * 30, 0) AS INT) AS CapacityRecMonthlyCost,
    CAST(ROUND((CASE
        WHEN b.TotalCUSec / NULLIF(b.DurationSec, 0) <= 2 THEN 2
        WHEN b.TotalCUSec / NULLIF(b.DurationSec, 0) <= 4 THEN 4
        WHEN b.TotalCUSec / NULLIF(b.DurationSec, 0) <= 8 THEN 8
        WHEN b.TotalCUSec / NULLIF(b.DurationSec, 0) <= 16 THEN 16
        WHEN b.TotalCUSec / NULLIF(b.DurationSec, 0) <= 32 THEN 32
        WHEN b.TotalCUSec / NULLIF(b.DurationSec, 0) <= 64 THEN 64
        WHEN b.TotalCUSec / NULLIF(b.DurationSec, 0) <= 128 THEN 128
        WHEN b.TotalCUSec / NULLIF(b.DurationSec, 0) <= 256 THEN 256
        WHEN b.TotalCUSec / NULLIF(b.DurationSec, 0) <= 512 THEN 512
        WHEN b.TotalCUSec / NULLIF(b.DurationSec, 0) <= 1024 THEN 1024
        WHEN b.TotalCUSec / NULLIF(b.DurationSec, 0) <= 2048 THEN 2048
        ELSE 0
    END) * {regional_pricing_per_cu} * 24 * 365, 0) AS INT) AS CapacityRecYearlyCost
FROM [{item_name}].[queryinsights].[exec_requests_history] a
INNER JOIN [{cost_analyzer_lakehouse}].[dbo].[silver_dw_lh_queries] b
ON a.distributed_statement_id = b.OperationID
WHERE a.distributed_statement_id IS NOT NULL AND b.DurationSec > 0 AND a.status = 'Succeeded'"""
    
    query_parts.append(query_part)

# Combine all query parts into one T-SQL query with UNION ALL
final_query_with_join = " UNION ALL ".join(query_parts)

# Wrap the final query with the WITH clause and SELECT statement, sorted by start_time
final_tsql_query = f"""
WITH Metrics AS (
{final_query_with_join}
)
SELECT 
    DataItem,
    distributed_statement_id,
    login_name,
    command,
    start_time,
    end_time,
    DurationSec,
    ROUND(DurationSec / 3600, 5) AS DurationHr,
    TotalCUs,
    ExpectedCUsPerSec,
    ActualCUsPerSec,
    IsBursting,
    BurstingMultiplier,
    RegionalCUPerHourCost,
    {regional_pricing_per_cu} * ROUND(DurationSec / 3600, 5) * ExpectedCUsPerSec AS ExpectedCostQuery,
    {regional_pricing_per_cu} * ROUND(DurationSec / 3600, 5) * ActualCUsPerSec AS ActualCostQuery,
    CapacityUsed,
    CapacityRec,
    CapacityUsedMonthlyCost,
    CapacityUsedYearlyCost,
    CapacityRecMonthlyCost,
    CapacityRecYearlyCost
FROM Metrics
ORDER BY start_time;
"""

# Print the final T-SQL query with join
print(final_tsql_query)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ###### Copy the T-SQL code above and run it via the Lakehouse SQL Endpoint of the Lakehouse attached to this notebook. This will allow you to join the information from the Capacity Metrics App to the Query Insights DMV.
