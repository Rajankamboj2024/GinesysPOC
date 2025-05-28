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

# MARKDOWN ********************

# #### **Import Libraries**

# CELL ********************

import pandas as pd
import requests
import json
from pyspark.sql.functions import col
import sempy.fabric as fabric
from requests import status_codes
import time

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
    customerworkspace = "DemoCustomer"

# Optional: Ensure it's still set if it was None
if customerworkspace is None:
    customerworkspace = "DemoCustomer"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### **Onboard Lakehouse Path**

# CELL ********************

#Get current Workspace Details
workspace_id=fabric.get_notebook_workspace_id()
print(workspace_id)

workspaces=fabric.list_workspaces()
current_workspace=workspaces[workspaces.Id == workspace_id]
workspace_name=current_workspace['Name'].iloc[-1]
print(workspace_name)

lakehousepath="abfss://"+workspace_name+"@onelake.dfs.fabric.microsoft.com/OnBoardingLakehouse.Lakehouse/"
tablepath=f"{lakehousepath}Tables/"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### **Generate Access Token**


# CELL ********************

# ---------------will use Azure Key vault
tenant_id = ""
client_id =  ""
client_secret = ""

auth_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"

auth_data = {
    'grant_type': 'client_credentials',
    'client_id': client_id,
    'client_secret': client_secret,
    'scope': 'https://analysis.windows.net/powerbi/api/.default'
    
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

# 
# #### **Set up headers with the obtained access token**

# CELL ********************

headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {access_token}'
}

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# 
# #### **Read the config_onboarding table**

# CELL ********************

config_onboarding_df = spark.sql(f"SELECT * FROM OnBoardingLakehouse.config_onboarding where CustomerName = '{customerworkspace}'")
# display(config_onboarding_df)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ### **Functions**

# MARKDOWN ********************

# #### **Eventhouse Creation** 

# CELL ********************

# Function to fetch existing eventhouses
def fetch_existing_eventhouses(workspace_id, headers):
    eventhouse_api_url = f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/eventhouses"
    response = requests.get(eventhouse_api_url, headers=headers)

    if response.status_code != 200:
        print(f"Failed to fetch Eventhouses for workspace {workspace_id}. Error: {response.text}")
        return []
    
    return response.json().get('value', [])

# Function to fetch eventhouse id
def fetch_eventhouse_id(eventhouse_name):
    eventhouse_api_url = f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/eventhouses"   
    response = requests.get(eventhouse_api_url, headers=headers)
    #response.raise_for_status()
    
    eventhouses = response.json().get("value", [])  # Assuming response has a "value" list
    
    for eventhouse in eventhouses:
        if eventhouse.get("displayName") == eventhouse_name:
            return eventhouse.get("id")
    
    return None  # Return None if eventhouse is not found

# Function to create an eventhouse if it doesn't exist
def create_eventhouse_if_needed(workspace_id, eventhouse_name, customer_name, headers):
    existing_eventhouses = fetch_existing_eventhouses(workspace_id, headers)
    eventhouse_names = {eventhouse['displayName'] for eventhouse in existing_eventhouses}

    if eventhouse_name in eventhouse_names:
        print(f"Eventhouse '{eventhouse_name}' already exists in workspace {workspace_id}.")
    else:
        print(f"Creating Eventhouse '{eventhouse_name}' in workspace {workspace_id}...")
        create_eventhouse_url = f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/eventhouses"
        payload = {
            "displayName": eventhouse_name,
            "description": f"Eventhouse for {customer_name}"
        }
        create_response = requests.post(create_eventhouse_url, headers=headers, json=payload)

        if create_response.status_code == 201:
            print(f"Eventhouse '{eventhouse_name}' created successfully.")
        else:
            print(f"Failed to create Eventhouse '{eventhouse_name}'. Error: {create_response.text}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### **Lakehouse Creation**

# CELL ********************

# Function to fetch existing lakehouses
def fetch_existing_lakehouses(workspace_id, headers):
    lakehouse_api_url = f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/lakehouses"
    response = requests.get(lakehouse_api_url, headers=headers)

    if response.status_code != 200:
        print(f"Failed to fetch Lakehouses for workspace {workspace_id}. Error: {response.text}")
        return []
    
    return response.json().get('value', [])

# Function to create a lakehouse if it doesn't exist
def create_lakehouse_if_needed(workspace_id, lakehouse_name, headers):
    existing_lakehouses = fetch_existing_lakehouses(workspace_id, headers)
    lakehouse_names = {lakehouse['displayName'] for lakehouse in existing_lakehouses}

    for lakehouse in existing_lakehouses:
        if lakehouse['displayName'] == lakehouse_name:
            print(f"Lakehouse Name '{lakehouse_name}',  Lakehouse Id {lakehouse['id']}  already exists in workspace {workspace_id}.")
            return lakehouse['id']  

            
    else:
        print(f"Creating Lakehouse '{lakehouse_name}' in workspace {workspace_id}...")
        create_lakehouse_url = f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/lakehouses"
        payload = {
            "displayName": lakehouse_name,
            "description": f"Lakehouse for {lakehouse_name}"
        }
        create_response = requests.post(create_lakehouse_url, headers=headers, json=payload)
        print(create_response.status_code)

        if create_response.status_code == 201:
            new_lakehouse = create_response.json()
            print(f"Lakehouse Name '{lakehouse_name}',  Lakehouse Id {new_lakehouse['id']}  created successfully.")
            return new_lakehouse['id']  # Return the ID of the newly created lakehouse

        else:
            print(f"Failed to create Lakehouse '{lakehouse_name}'. Error: {create_response.text}")


    

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ##### **KQL Table Creation**

# CELL ********************

def create_kql_table(workspace_id,eventhouse_id,database_name,kqltablename,headers):
    # print(f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/eventhouses/{eventhouse_id}")

    kql_query_uri = requests.get(
    f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/eventhouses/{eventhouse_id}",
        headers = headers
    ).json().get('properties').get('queryServiceUri')

    # print(kql_query_uri)

    # Get KQL access token
    auth_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/token"
    auth_data = {
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret,
        'resource': 'https://api.kusto.windows.net'
        
    }
    response = requests.post(auth_url, data=auth_data)
    kql_access_token = response.json().get("access_token")

    # print(response)
    # print(kql_access_token)

    #---------------------------------------------------Check Table Exists----------------------------------------------------

    check_query = f'.show tables | where TableName has "{kqltablename}"'

    # print(check_query)

    check_table = requests.post(
        f"{kql_query_uri}/v1/rest/mgmt",
        json={'csl': check_query, 'db': database_name},
        headers={
            "Authorization": f"Bearer {kql_access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    )

    result = check_table.json()
    # print(result)
    if result.get('Tables') and result['Tables'][0].get('Rows'):
        print(f"KQL Table '{kqltablename}'  already exists in database '{database_name}'")
        return


    #---------------------------------------------------Create Table -----------------------------------------------------

    # Execute create table command
    kql_query = f".create table [{kqltablename}] (schema:dynamic, payload:dynamic, ingestion_datetime:datetime)"
    create_table = requests.post(
        f"{kql_query_uri}/v1/rest/mgmt",
        json={
            'csl': kql_query,
            'db': database_name
        },
        headers={
            "Authorization": f"Bearer {kql_access_token}",  # Use the token from previous steps
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    )

    if create_table.status_code == 200:
        print(f"Table '{kqltablename}' created successfully.")
    else:
        print(f"Error creating table '{kqltablename}':", create_table.text)

    # print(create_table)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ##### **Get KQL DatabaseItemsId**

# CELL ********************

def get_kql_db_id_from_eventhouse(workspace_id, eventhouse_id, headers):
    eventhouse_url = f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/eventhouses/{eventhouse_id}"
    
    response = requests.get(eventhouse_url, headers=headers)
    
    if response.status_code != 200:
        print(f" Failed to fetch Eventhouse info: {response.text}")
        return None

    eventhouse_info = response.json()
    # print(eventhouse_info)
    db_id = eventhouse_info.get("properties", {}).get("databasesItemIds")

    if db_id:
        print(f"KQL Database ID:  {db_id[0]}")
        # print(db_id)
        return db_id[0]
    else:
        print(" No databaseId found in Eventhouse properties.")
        return None


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### **Create shortcut (Moved to Manual Script)** 

# CELL ********************

# def create_shortcut(workspace_id,lakehouse_id,eventhouse_id,database_id,kqltablename,headers):
#     table_name = f"{kqltablename}"

#     # action, shortcut_path, shortcut_name, target
#     request_body = {
#             "path": "Tables",
#             "name": table_name,
#             "target": {
#                 "OneLake": {
#                     "workspaceId": workspace_id,
#                     "itemId": database_id,
#                     "path": "Tables/" +  table_name
#                 }
#             }
#         }

#     response = requests.request(
#         method = "POST", 
#         url = f'https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/items/{lakehouse_id}/shortcuts?shortcutConflictPolicy=Abort', 
#         headers = headers, 
#         json = request_body)

#     if response.status_code == 201:
#         print(f"Shortcut created successfully.")
#     else:
#         print(f"{response.text}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### **Execution** 

# CELL ********************

# Iterate through each customer eventhouse from the config_onboarding table
for row in config_onboarding_df.collect():
    customer_name = row['CustomerName']
    workspace_id = row['WorkspaceId']
    print(f"----------Processing workspace {workspace_id} for customer {customer_name}------------")
    
    # Format the Eventhouse name
    eventhouse_name = f"Eventhouse_{customer_name}"
    
    # ------------------------------------------------------------------------------Create the Eventhouse if needed
    create_eventhouse_if_needed(workspace_id, eventhouse_name, customer_name, headers)

    # ------------------------------------------------------------Check and create the 'BronzeLayer' and 'LandingLayer' lakehouses
    bronze_lakehouse_id=create_lakehouse_if_needed(workspace_id, "BronzeLayer", headers)
    landing_lakehouse_id=create_lakehouse_if_needed(workspace_id, "LandingLayer", headers)

    # Get the eventhouse id
    eventhouse_id = fetch_eventhouse_id(eventhouse_name)
    # print(eventhouse_id)

    # ------------------------------------------------------------------Create the kql table in eventhouse
    kqltablename = "raw" + "_" + customer_name

    # print(kqltablename)
    database_name = f"Eventhouse_{customer_name}"
    # print(database_name)

    create_kql_table(workspace_id,eventhouse_id,database_name,kqltablename,headers)

    # ------------------------------------------------------------------Get kql database id
    database_id=get_kql_db_id_from_eventhouse(workspace_id, eventhouse_id, headers)

    # ------------------------------------------------------------------Create shortcut into landing lakehouse

    # create_shortcut(workspace_id,landing_lakehouse_id,eventhouse_id,database_id,kqltablename,headers)

    print(f"----------All items created in workspace {workspace_id} for customer {customer_name}---------------")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
