from fastapi import FastAPI ,Request, Form
from bson import ObjectId
from google import genai
import os
from dotenv import load_dotenv
from fastapi.responses import HTMLResponse,RedirectResponse
from fastapi.templating import Jinja2Templates
from pymongo import MongoClient
from datetime import datetime
from fastapi.staticfiles import StaticFiles

load_dotenv()

app=FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

mongo_client = MongoClient(os.getenv("MONGO_URI"))
db = mongo_client["chat_db"]
collection = db["conversations"]

#home page
@app.get("/",response_class=HTMLResponse)
def home(request: Request):
    chats = list(collection.find().sort("created_at", -1).limit(20))
    return templates.TemplateResponse("index.html", {"request": request, "chats":chats, "current_chat": None})

# create new chat
@app.get("/new")
def new_chat():
    last_chat = collection.find_one(sort=[("created_at", -1)])
    if not last_chat:
        result=collection.insert_one({"title":"New Chat", "created_at": datetime.now(), "messages": []})
    
    return RedirectResponse(f"/chat/{result.inserted_id}", status_code=302)

    if len(last_chat["messages"]) == 0:
        return RedirectResponse(f"/chat/{last_chat['_id']}", status_code=302 )
    
    result=collection.insert_one({"title":"New Chat", "created_at": datetime.now(), "messages": []})
    return RedirectResponse(f"/chat/{result.inserted_id}", status_code=302)

#add a get router
@app.get("/chat/{chat_id}",response_class=HTMLResponse)
def open_chat(request: Request, chat_id: str):
    chats = list(collection.find().sort("created_at", -1))
    current_chat=collection.find_one({"_id": ObjectId(chat_id)})
    return templates.TemplateResponse("index.html", {"request": request, "chats": chats, "current_chat": current_chat})

# send message to specific chat
@app.post("/chat/{chat_id}",response_class=HTMLResponse)
def send_message(request: Request, chat_id: str, question: str = Form(...)):
    response=client.models.generate_content(
    
        model="gemini-3-flash-preview",
        contents=question   
        )
    answer=response.text

    collection.update_one(
        {"_id": ObjectId(chat_id)},
        {"$push": {"messages": {"question": question, "answer": answer, "timestamp": datetime.now()}},
         "$set":{
             "title": question[:30]  
         }
         }
    )
    return RedirectResponse(f"/chat/{chat_id}", status_code=302)