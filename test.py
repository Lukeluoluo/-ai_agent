from dotenv import load_dotenv
import os

load_dotenv()

print("DEEPSEEK_API_KEY:", os.getenv("DEEPSEEK_API_KEY"))
print("AMAP_API_KEY:", os.getenv("AMAP_API_KEY"))
print("TAVILY_API_KEY:", os.getenv("TAVILY_API_KEY"))
