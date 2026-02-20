from fastapi import FastAPI
from pydantic import BaseModel
from google import genai
import os
from dotenv import load_dotenv

load_dotenv()
                  
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

app=FastAPI()

class Question(BaseModel):
    question: str
@app.get("/")
def home():
    return {"message": "Chatbot is running"}

@app.post("/chat")
def chat(q: Question):
    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=q.question
    )
    return{
        "question": q.question,
        "answer": response.text
    }
