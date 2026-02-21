from fastapi import FastAPI ,Request, Form
from pydantic import BaseModel
from google import genai
import os
from dotenv import load_dotenv
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

load_dotenv()

app=FastAPI()

templates = Jinja2Templates(directory="templates")
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

@app.get("/",response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "answer":"", "question": ""})

@app.post("/chat",response_class=HTMLResponse)
def chat(request:Request, question:str=Form(...)):
    try:
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=question
        )
        answer = response.text

    except Exception as e:
        answer = f"Error: {str(e)}"
        
    return templates.TemplateResponse("index.html", {"request": request, "answer": answer, "question": question})
    
        
