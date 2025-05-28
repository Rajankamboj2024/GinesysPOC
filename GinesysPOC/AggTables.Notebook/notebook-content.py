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

path="abfss://c5672fc9-2a13-4083-9a9e-caa93efa804f@onelake.dfs.fabric.microsoft.com/3c42cbd7-13ba-470b-b652-04a5ed96e475/Tables/"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### Item

# CELL ********************

df=spark.sql("""

WITH CTE AS(
SELECT 
    INVITEM.icode AS  ICODE,
    INVGRP.lev1grpname AS DIVISION,
    INVGRP.lev2grpname AS SECTION,
    INVGRP.grpname AS DEPARTMENT,
    INVITEM.cname1 AS CATEGORY1,
    INVITEM.cname2 AS CATEGORY2,
    INVITEM.cname3 AS CATEGORY3,
    INVITEM.cname4 AS CATEGORY4,
    INVITEM.cname5 AS CATEGORY5,
    INVITEM.cname6 AS CATEGORY6,
    INVITEM.listed_mrp AS MRP,
    INVITEM.mrp AS RSP,
    INVITEM.invarticle_code AS invarticle_code
  
FROM 
    BronzeLayer.invitem AS INVITEM 
JOIN 
    BronzeLayer.invgrp AS INVGRP 
    ON INVITEM.grpcode = INVGRP.grpcode
    where INVITEM.deleteflag=0 and INVGRP.deleteflag=0
),

CTEfinal AS
(
Select CTE.*, 
BronzeLayer.invarticle.name AS ARTICLE from 
BronzeLayer.invarticle JOIN CTE
    ON  CTE.invarticle_code = invarticle.code 
     where invarticle.deleteflag=0 
    )

SELECT * FROM CTEfinal;


""")

df.write.mode("overwrite").save(f"{path}vw_ITEM")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### Site

# CELL ********************

df=spark.sql("""

SELECT 
ADMSITE.code AS CODE,
ADMSITE.name AS LONG_NAME,
ADMSITE.shrtname AS SHORT_NAME,
ADMSITE.sitetype AS SITE_TYPE,
ADMCITY.ctname AS CITY,
ADMCITY.stname AS STATE,
ADMCITY.cnname AS COUNTRY,
ADMCITY.zone AS ZONE
FROM BronzeLayer.admsite AS ADMSITE
LEFT JOIN BronzeLayer.admcity as ADMCITY
ON ADMSITE.ctname = ADMCITY.ctname
where ADMSITE.deleteflag=0 and ADMCITY.deleteflag=0

""")

df.write.mode("overwrite").save(f"{path}vw_SITE")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ##### Stock

# CELL ********************

df=spark.sql("""

WITH base_data AS (
    SELECT
        admsite_code,
        icode,
        entdt,
        SUM(CASE WHEN qty > 0 THEN qty ELSE 0 END) AS inward_stock,
        SUM(CASE WHEN qty < 0 THEN qty ELSE 0 END) AS outward_stock
    FROM invstock where deleteflag=0
    GROUP BY admsite_code, icode, entdt
),
ordered_data AS (
    SELECT
        admsite_code,
        icode,
        entdt,
        inward_stock,
        outward_stock,
        ROW_NUMBER() OVER (PARTITION BY admsite_code, icode ORDER BY entdt) AS rn
    FROM base_data
),
running_totals AS (
    SELECT
        admsite_code,
        icode,
        entdt,
        inward_stock,
        outward_stock,
        SUM(inward_stock + outward_stock) OVER (
            PARTITION BY admsite_code, icode
            ORDER BY entdt
            ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
        ) AS opening_stock,
        SUM(inward_stock + outward_stock) OVER (
            PARTITION BY admsite_code, icode
            ORDER BY entdt
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS closing_stock
    FROM ordered_data
)
SELECT
    admsite_code AS SITE_CODE,
    icode AS ITEM_CODE,
   CAST(entdt as DATE) AS ENTRY_DATE,
    coalesce(opening_stock, 0) AS OPENING_STOCK,
    inward_stock AS INWARD_STOCK,
    outward_stock AS OUTWARD_STOCK,
    closing_stock AS CLOSING_STOCK
FROM running_totals

""")

df.write.mode("overwrite").save(f"{path}vw_STOCKBOOKAGG1")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ##### psite_posbillitem

# CELL ********************

df=spark.sql("""

SELECT 
    A.*,B.psite_customer_code as psite_customer_code,
    CAST(ref_billdate AS DATE) AS ref_billdate_cast
FROM BronzeLayer.psite_posbillitem  A
join BronzeLayer.psite_posbill B on A.psite_posbill_code=B.code and  A.admsite_code=B.admsite_code

WHERE A.deleteflag = 0 and B.deleteflag = 0


""")

df.write.mode("overwrite").save(f"{path}vw_psite_posbillitem")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
