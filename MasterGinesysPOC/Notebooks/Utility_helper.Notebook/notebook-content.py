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
# META         },
# META         {
# META           "id": "28f7e917-3e52-4fa7-89cf-1b43064b4a19"
# META         }
# META       ]
# META     }
# META   }
# META }

# MARKDOWN ********************

# ###### **Copy file between workspaces (Lakehouse to Lakehouse)**

# CELL ********************

from pyspark.sql import SparkSession

# Initialize Spark session
spark = SparkSession.builder.getOrCreate()

# Define source and destination paths in OneLake
source_workspace = ""
destination_workspace = ""  # Ensure this variable is defined
file_name = ""

# OneLake paths
source_path = f"abfss://{source_workspace}@onelake.dfs.fabric.microsoft.com/OnBoardingLakehouse.Lakehouse/Files/Notebooks/{file_name}"
destination_path = f"abfss://{destination_workspace}@onelake.dfs.fabric.microsoft.com/BronzeLayer.Lakehouse/Files/Notebooks/{file_name}"

print("Source Path:", source_path)
print("Destination Path:", destination_path)

# Use dbutils to copy the file directly
notebookutils.fs.cp(source_path, destination_path)

print(f"File '{file_name}' copied successfully from '{source_workspace}' to '{destination_workspace}'")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ###### **Generate access token for Fabric REST API scope**

# CELL ********************

# ---------------will use Azure Key vault
import requests

tenant_id = ""
client_id =  ""
client_secret = ""

auth_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"

auth_data = {
    'grant_type': 'client_credentials',
    'client_id': client_id,
    'client_secret': client_secret,
    'scope': 'https://api.fabric.microsoft.com/.default'
    
}

response = requests.post(auth_url, data=auth_data)

access_token= response.json().get("access_token")
if response.status_code == 200:
    print("Access token generated") #, response.json().get("access_token"))
else:
    print(f"Failed to get token: {response.status_code} - {response.text}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ###### **Copy notebook item from one workspace to another**

# CELL ********************

# Headers
headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
}

# Source workspace and notebook
source_workspace_id = "10f72987-5056-4f76-80a2-bf50df0fdc12"
source_notebook_name = "DynamicWorkspaceLakehouseName"

# Export the notebook
url_notebooks = f"https://api.fabric.microsoft.com/v1/workspaces/{source_workspace_id}/notebooks"

response = requests.get(url_notebooks, headers=headers)
notebook_content = response.json()

# Destination workspace
destination_workspace_id = "43eaef67-2568-4a09-99f3-4d67c6b17148"
import_url = f"https://api.fabric.microsoft.com/v1/workspaces/{destination_workspace_id}/notebooks/"

# Import the notebook into destination workspace
payload = {
    "displayName": source_notebook_name
}

import_response = requests.post(import_url, headers=headers, json=payload)

if import_response.status_code == 201:
    print("Notebook copied successfully.")
else:
    print("Error:", import_response.text)


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ###### **Get dynamically workspace and lakehouse name**

# CELL ********************

#Generate Dynamically Lakehouse and Workspace Name
import sempy.fabric as fabric

lakehouse_name = ""
workspace_name = ""

#Get Workspace Name
wid=fabric.get_notebook_workspace_id()
print(wid)

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

# MARKDOWN ********************

# ###### **Key vault code**

# CELL ********************

# from azure.identity import DefaultAzureCredential
# from azure.keyvault.secrets import SecretClient

# key_vault_name = "your-keyvault-name"
# secret_name = "your-secret-name"

# credential = DefaultAzureCredential()
# kv_uri = f"https://{key_vault_name}.vault.azure.net"

# client = SecretClient(vault_url=kv_uri, credential=credential)
# retrieved_secret = client.get_secret(secret_name)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# import pandas as pd
# from pyspark.sql.functions import col, when, max, coalesce, lit, create_map
# from delta.tables import DeltaTable
# from itertools import chain###### **Delta table creation from dataframe**

# CELL ********************

import pandas as pd
from pyspark.sql.functions import col, when, max, coalesce, lit, create_map
from delta.tables import DeltaTable
from itertools import chain

masterlakehousepath="abfss://MasterGinesys@onelake.dfs.fabric.microsoft.com/OnBoardingLakehouse.Lakehouse/"
masterlakehousetablepath = f"{masterlakehousepath}Tables/"

# Read onboarding configuation file
pandas_df_onboard=pd.read_excel(f"{masterlakehousepath}Files/Config/MasterConfigurations.xlsx",sheet_name="onboarding")
config_df_onboard=spark.createDataFrame(pandas_df_onboard)

delta_table_onboard='config_onboarding'
config_df_onboard.write.mode("overwrite").option("mergeSchema","True").format("delta").saveAsTable(delta_table_onboard)

# Read table master list configuation file
# pandas_df_metadata=pd.read_excel(f"{masterlakehousepath}Files/Config/MasterConfigurations.xlsx",sheet_name="mastertablelist")
# config_df_metadata=spark.createDataFrame(pandas_df_metadata)

# delta_table_metadata='config_mastertablelist'
# config_df_metadata.write.mode("overwrite").format("delta").saveAsTable(delta_table_metadata)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ##### **Mounting OneLake Containers in Microsoft Fabric**

# CELL ********************



# Mount Bronze Layer to a specific mount point
mssparkutils.fs.mount(
    f"abfss://{workspace_name}@onelake.dfs.fabric.microsoft.com/BronzeLayer.Lakehouse",
    "/lakehouse/BronzeLayer"
)

# Mount Landing Layer to a different mount point
mssparkutils.fs.mount(
    f"abfss://{workspace_name}@onelake.dfs.fabric.microsoft.com/LandingLayer.Lakehouse",
    "/lakehouse/LandingLayer"
)


# # List current mounts 
# mssparkutils.fs.mounts()
mounts = mssparkutils.fs.mounts()
for m in mounts:
    print(m.mountPoint)


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
