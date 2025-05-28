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
# META       "default_lakehouse_workspace_id": "10f72987-5056-4f76-80a2-bf50df0fdc12"
# META     }
# META   }
# META }

# CELL ********************

#Generate Dynamically Lakehouse and Workspace Name
import sempy.fabric as fabric

lakehouse_name = ""
workspace_name = ""

#Get Workspace Name
wid=fabric.get_notebook_workspace_id()

workspaces=fabric.list_workspaces()
current_workspace=workspaces[workspaces.Id == wid]
workspace_name=current_workspace['Name'].iloc[-1]


#Get Lakehosue Name  
lakehouselist= [lakehouse for lakehouse in notebookutils.lakehouse.list() if "Lakehouse" in lakehouse.displayName]

for lakehouse in lakehouselist :
    lakehouse_name = lakehouse.displayName

#Print 

print(f"Workspace : {workspace_name}")
print(f"Lakehouse : {lakehouse_name}")

#Generate lakehouse  File Path and Table Path
LakehouseFilePath=f"abfss://{workspace_name}@onelake.dfs.fabric.microsoft.com/{lakehouse_name}.Lakehouse/Files/"
LakehouseTablePath=f"abfss://{workspace_name}@onelake.dfs.fabric.microsoft.com/{lakehouse_name}.Lakehouse/Tables/"

print(f"Filepath : {LakehouseFilePath}")
print(f"Tablepath : {LakehouseTablePath}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
