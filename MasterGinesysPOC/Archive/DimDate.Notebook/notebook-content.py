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
# META         }
# META       ]
# META     }
# META   }
# META }

# CELL ********************



df=spark.sql("""select CAST(min(entdt) as DATE) as MinDate, CAST(MAX(entdt) as DATE) as MaxDate from invstock """)
display(df)


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

#-------DIM DATE
from pyspark.sql import functions as F
from pyspark.sql.functions import col
from pyspark.sql.types import StructType, StructField, IntegerType, StringType, DoubleType, TimestampType



df=spark.sql("""select CAST(min(entdt) as DATE) as MinDate, CAST(MAX(entdt) as DATE) as MaxDate from invstock """)

# Get the min and max ENTRY_DATE from df
min_date =  df.agg(F.min("MinDate")).collect()[0][0]
max_date = df.agg(F.max("MaxDate")).collect()[0][0]

print(min_date)
print(max_date)

# Create a date range from min_date to max_date
date_range = spark.sql("""
    SELECT explode(sequence(to_date('{}'), to_date('{}'), interval 1 day)) AS Date
""".format(min_date, max_date))

# Add additional columns for Year, Month, Day, Quarter, and Weekday
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

# Define table name
table_name = 'DimDate'

# Save the DataFrame as a Delta table
date_table.write.mode("overwrite").format("delta").save("Tables/" + table_name)

display(date_table)


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
