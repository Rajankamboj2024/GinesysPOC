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
from pyspark.sql.functions import col, when, max, coalesce, lit, create_map
from delta.tables import DeltaTable
from itertools import chain
import sempy.fabric as fabric

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ##### **Define Parameters**

# CELL ********************

# customerworkspace = ""
# capacityid = ""

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ##### **Onboard Lakehouse Path**

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

# #### **Read ConfigOnBoarding**

# CELL ********************

pandas_df_onboard=pd.read_excel(f"{lakehousepath}Files/Config/MasterConfigurations.xlsx",sheet_name="onboarding")
config_df_onboard=spark.createDataFrame(pandas_df_onboard)
config_df_onboard = config_df_onboard.filter(col("CustomerName")==customerworkspace).withColumn("WorkspaceId", lit(''))
delta_table_name='config_onboarding'

#Update WorkspaceId into  config_onboarding
delta_path = f"{tablepath}{delta_table_name}"
delta_table = DeltaTable.forPath(spark, delta_path)

# config_df_onboard.printSchema()
# delta_table.toDF().printSchema()

# Perform UPSERT (MERGE)
delta_table.alias("target").merge(
    config_df_onboard.alias("source"),
    "target.CustomerName = source.CustomerName"
).whenMatchedUpdate(
    condition="target.OnboardingStatus != 'completed'",  # Skip updates if OnboardingStatus is "completed"
    set={col_name: col(f"source.{col_name}") for col_name in config_df_onboard.columns}  # Update all columns dynamically
).whenNotMatchedInsertAll().execute()  # Insert all if new

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ### **Generate Access Token**


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

# #### **Workspace :  Creation , Assign Capacity and Adding Users**


# CELL ********************

import requests
import pandas as pd

capacity_id = capacityid

headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {access_token}'
}

# Read the config_onboarding table
config_onboarding_df =spark.sql(f"SELECT * FROM OnBoardingLakehouse.config_onboarding where CustomerName='{customerworkspace}'")

# Power BI REST API endpoint to fetch existing workspaces
workspace_api_url = "https://api.powerbi.com/v1.0/myorg/groups"
existing_workspaces = requests.get(workspace_api_url, headers=headers).json().get('value', [])
existing_workspace_dict = {workspace['name']: workspace['id'] for workspace in existing_workspaces}

# Iterate through each workspace from the config_onboarding table

for row in config_onboarding_df.collect():
    workspace_name = row['CustomerName']
    workspace_description = f"Workspace for {workspace_name}"
    user_emails = [email.strip().lower() for email in row['PowerBIUserList'].split(',')]  # Split emails and convert to lowercase
    
    workspace_id = existing_workspace_dict.get(workspace_name)
    
    # If workspace does not exist, create it
    if not workspace_id:
        print(f"Creating workspace: {workspace_name}")
        # Workspace details
        workspace_data = {
            "name":  workspace_name,
            "description": workspace_description,
            "type": "Workspace",
            "isOnDedicatedCapacity": True,
            "capacityId": capacity_id
        }

        response = requests.post(workspace_api_url, headers=headers, json=workspace_data)
        
        if response.status_code == 200:
            workspace_id = response.json().get('id')
            existing_workspace_dict[workspace_name] = workspace_id
            print(f"------------------------------Workspace created successfully, ID: {workspace_id}-------------------------")

            # -------------------------------------------Power BI API endpoint for assigning a workspace to a capacity
            assign_capacity_url = f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/assignToCapacity"

                        # Set up the headers with the access token
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}"
            }

            # Define the payload (JSON body)
            payload = {
                "capacityId": capacity_id
            }

            # Make the POST request
            response = requests.post(assign_capacity_url, headers=headers, json=payload)

            # Print response details
            if response.status_code == 202:
                print(f"Workspace {workspace_id} successfully assigned to capacity {capacity_id}.")
            else:
                print(f"Failed to assign workspace to capacity: {response.status_code} - {response.text}")

        else:
            print(f"Failed to create workspace: {response.status_code} - {response.text}")
            continue  # Skip adding users if workspace creation fails
    else:
        print(f"Workspace already exists: {workspace_name}, ID: {workspace_id}")
    
    # Get existing users in the workspace
    users_in_workspace_url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/users"
    existing_users_response = requests.get(users_in_workspace_url, headers=headers)
    existing_users = []
    
    if existing_users_response.status_code == 200:
        existing_users = [user.get('emailAddress', user.get('identifier')) for user in existing_users_response.json().get('value', [])]
        existing_users = {user.lower() for user in existing_users}
        print(existing_users)
    else:
        print(f"Failed to retrieve users for workspace {workspace_name}: {existing_users_response.status_code} - {existing_users_response.text}")
    
    # Loop through users and add if not already in the workspace
    for user_email in user_emails:
        user_email = user_email.strip()  # Remove any extra spaces
        
        if user_email in existing_users:
            print(f"User {user_email} already exists in workspace {workspace_name}.")
            continue
        
        # print(f"Adding user {user_email} to workspace {workspace_name}.")
        add_user_url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/users"
        user_data = {
            "emailAddress": user_email,
            "groupUserAccessRight": "Admin"  # Change role if needed
        }
        add_user_response = requests.post(add_user_url, headers=headers, json=user_data)
        
        if add_user_response.status_code == 200:
            print(f"User {user_email} added successfully")
        else:
            print(f"Failed to add user {user_email}: {add_user_response.status_code} - {add_user_response.text}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### **Update WorkspaceId into config_onboarding**

# CELL ********************

config_onboarding_df =spark.sql("SELECT * FROM OnBoardingLakehouse.config_onboarding")

# Power BI REST API endpoint to fetch existing workspaces
workspace_api_url = "https://api.powerbi.com/v1.0/myorg/groups"
existing_workspaces = requests.get(workspace_api_url, headers=headers).json().get('value', [])

# Convert workspace names to a dictionary {workspace_name: workspace_id}
existing_workspace_dict = {workspace['name']: workspace['id'] for workspace in existing_workspaces}

#-----* Run 1---------------------
# print(existing_workspace_dict)

# Convert dictionary to a list of key-value pairs for create_map()
mapping_expr = create_map([lit(x) for x in chain(*existing_workspace_dict.items())])

# Add "WorkspaceId" column dynamically based on CustomerName matching with workspace_dict
config_onboarding_df = config_onboarding_df.withColumn("WorkspaceId", mapping_expr.getItem(col("CustomerName")))

#-----* Run 2---------------------
# Display the updated DataFrame
display(config_onboarding_df)

#Overwrite with WorkspaceId
delta_table_name='config_onboarding'
config_onboarding_df.write.mode("overwrite").format("delta").saveAsTable(delta_table_name)


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### **Assign Capacity**

# CELL ********************

# import requests

# # Define your variables
# capacity_id='4E3295BC-6B52-4587-BCB9-21AF8518BE44'
# workspace_id = "4887b64a-855d-47ec-a287-49f82381b7ee"  # Replace with an existing workspace ID


# # Power BI API endpoint for assigning a workspace to a capacity
# assign_capacity_url = f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/assignToCapacity"

# # Set up the headers with the access token
# headers = {
#     "Content-Type": "application/json",
#     "Authorization": f"Bearer {access_token}"
# }

# # Define the payload (JSON body)
# payload = {
#     "capacityId": capacity_id
# }

# # Make the POST request
# response = requests.post(assign_capacity_url, headers=headers, json=payload)

# # Print response details
# if response.status_code == 202:
#     print(f"Workspace {workspace_id} successfully assigned to capacity {capacity_id}.")
# else:
#     print(f"Failed to assign workspace to capacity: {response.status_code} - {response.text}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### **Get Capacites Information**

# CELL ********************

# import requests


# # Power BI API endpoint to get capacities
# capacities_url = "https://api.powerbi.com/v1.0/myorg/capacities"

# # Headers for authentication
# headers = {
#     "Content-Type": "application/json",
#     "Authorization": f"Bearer {access_token}"
# }

# # Make the GET request
# response = requests.get(capacities_url, headers=headers)

# # Check response
# if response.status_code == 200:
#     capacities = response.json().get("value", [])
    
#     if capacities:
#         print("Available Capacities:")
#         for cap in capacities:
#             print(f"Name: {cap['displayName']}, ID: {cap['id']}, State: {cap['state']}")
#     else:
#         print("No capacities found.")
# else:
#     print(f"Failed to fetch capacities: {response.status_code} - {response.text}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### **Delete Workspace**

# CELL ********************

# import requests


# workspace_id = "69d8e540-512a-41a9-8faf-8c8dce40d392"  # Replace with the workspace ID you want to delete

# # Headers
# headers = {
#     "Content-Type": "application/json",
#     "Authorization": f"Bearer {access_token}"
# }

# # API endpoint to delete the workspace
# delete_workspace_url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}"

# # Make DELETE request
# response = requests.delete(delete_workspace_url, headers=headers)

# # Check response
# if response.status_code == 200:
#     print(f"Workspace {workspace_id} deleted successfully!")
# elif response.status_code == 403:
#     print("Permission Denied: You need admin access to delete the workspace.")
# elif response.status_code == 404:
#     print("Workspace not found. Please check the workspace ID.")
# else:
#     print(f"Failed to delete workspace: {response.status_code} - {response.text}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
