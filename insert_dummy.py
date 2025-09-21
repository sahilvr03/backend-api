from pymongo import MongoClient

# 1️⃣ Connect to MongoDB (local)
client = MongoClient("mongodb://localhost:27017")

# 2️⃣ Create/use database
db = client["lead_database"]

# 3️⃣ Create/use collection
leads_collection = db["new_leads"]

# 4️⃣ Dummy leads
dummy_leads = [
    # {
    #     "name": "Alice Johnson",
    #     "role": "CTO",
    #     "company": "Fintech Solutions",
    #     "email": "ilmasaleem02@gmail.com",
    #     "company_info": "A financial technology company providing mobile banking solutions.",
    #     "country": "United States"
    # },
    # {
    #     "name": "Ravi Kumar",
    #     "role": "Head of IT",
    #     "company": "AgriTech India",
    #     "email": "aleema4202812@cloud.neduet.edu.pk",
    #     "company_info": "Develops smart agriculture platforms for crop monitoring and yield prediction.",
    #     "country": "Saudi Arabia"
    # },
    # {
    #     "name": "Maria Lopez",
    #     "role": "CEO",
    #     "company": "HealthCare Analytics",
    #     "email": "ilmasaleem09@gmail.com",
    #     "company_info": "Provides AI-powered solutions for patient data management and predictive diagnosis.",
    #     "country": "United Kingdom"
    # },
    #     {
    #     "name": "sami",
    #     "role": "CEO",
    #     "company": "Agri tech pak",
    #     "email": "aleema4202812@cloud.neduet.edu.pk",
    #     "company_info": "Provides AI-powered solutions for Agri data management and predictive diagnosis.",
    #     "country": "Pakistan"
    # },
            {
        "name": "ilma",
        "role": "CEO",
        "company": "Packages tech ",
        "email": "ilmasaleem02@gmail.com",
        "company_info": "Provides AI-powered solutions for paper tech",
        "country": "Pakistan"
    }
]

# 5️⃣ Insert
result = leads_collection.insert_many(dummy_leads)
print(f"✅ Inserted {len(result.inserted_ids)} dummy leads into MongoDB")

# from pymongo import MongoClient

# # Connect to MongoDB
# client = MongoClient("mongodb://localhost:27017/")
# db = client["lead_database"]
# collection = db["leads"]

# # Remove the email_content field from all documents
# result = collection.update_many(
#     {},
#     {"$unset": {"email_content": ""}}
# )

# print(f"Modified {result.modified_count} documents.")
