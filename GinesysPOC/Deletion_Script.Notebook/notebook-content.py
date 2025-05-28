# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {}
# META }

# CELL ********************

from delta.tables import DeltaTable
from pyspark.sql import SparkSession
import sempy.fabric as fabric

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

#Get current Workspace Details
workspace_id=fabric.get_notebook_workspace_id()
print(workspace_id)

workspaces=fabric.list_workspaces()
current_workspace=workspaces[workspaces.Id == workspace_id]
workspace_name=current_workspace['Name'].iloc[-1]
print(workspace_name)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Get the list of table objects from the Lakehouse
delta_tables = spark.catalog.listTables("BronzeLayer")
delta_table_names = [table.name for table in delta_tables]

for table_name in delta_table_names:
    # Define Delta table path
    delta_table_path = f"abfss://"+workspace_name+"@onelake.dfs.fabric.microsoft.com/BronzeLayer.Lakehouse/Tables/"+table_name+""
    print(delta_table_path)

    # Load Delta Table
    delta_table = DeltaTable.forPath(spark, delta_table_path)

    # Perform delete operation
    delta_table.delete("deleteflag = 1")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
