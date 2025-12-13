from dotenv import load_dotenv
from google import genai
import os



def gemini_query(prompt):
    load_dotenv()
    key = os.getenv("GEMINI_API_KEY")


    client = genai.Client(api_key=key)

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    return response.text

