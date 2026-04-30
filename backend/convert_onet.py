import pandas as pd
import json

# load excel
df = pd.read_excel("backend/data/Occupation Data.xlsx")

careers = []

for _, row in df.iterrows():
    careers.append({
        "code": row["O*NET-SOC Code"],
        "title": row["Title"],
        "description": row["Description"]
    })

# save JSON
with open("backend/data/onet_careers.json", "w") as f:
    json.dump(careers, f, indent=2)

print("Done!")

