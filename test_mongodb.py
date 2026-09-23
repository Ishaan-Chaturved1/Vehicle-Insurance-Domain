import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

mongo_url = os.getenv("MONGODB_URL")

client = MongoClient(mongo_url)

try:
    client.admin.command("ping")
    print("MongoDB connected successfully!")

    db = client["vehicle_insurance"]
    print("Database:", db.name)

except Exception as e:
    print("MongoDB connection failed:", e)