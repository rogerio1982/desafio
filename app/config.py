import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
VECTOR_STORE_ID: str = os.getenv("VECTOR_STORE_ID", "")

client = OpenAI(api_key=OPENAI_API_KEY)
