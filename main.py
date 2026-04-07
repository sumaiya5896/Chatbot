from fastapi import FastAPI, Request, Form, File, UploadFile
from bson import ObjectId
from google import genai
import os
from dotenv import load_dotenv
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pymongo import MongoClient
from datetime import datetime
from fastapi.staticfiles import StaticFiles
import emoji
import re
import markdown

load_dotenv()

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

mongo_client = MongoClient(os.getenv("MONGO_URI"))
db = mongo_client["chat_db"]
collection = db["conversations"]

# Home page
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    chats = list(collection.find().sort("created_at", -1).limit(20))
    return templates.TemplateResponse("index.html", {"request": request, "chats": chats, "current_chat": None})

# Create new chat
@app.get("/new")
def new_chat():
    # Create a new chat with a default title
    result = collection.insert_one({"title": "New Chat", "created_at": datetime.now(), "messages": []})
    return RedirectResponse(f"/chat/{result.inserted_id}", status_code=302)

# Open a specific chat
@app.get("/chat/{chat_id}", response_class=HTMLResponse)
def open_chat(request: Request, chat_id: str):
    chats = list(collection.find().sort("created_at", -1))
    current_chat = collection.find_one({"_id": ObjectId(chat_id)})
    return templates.TemplateResponse("index.html", {"request": request, "chats": chats, "current_chat": current_chat})

# Send message to specific chat
@app.post("/chat/{chat_id}", response_class=HTMLResponse)
def send_message(request: Request, chat_id: str, question: str = Form(...)):
    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=question
    )
    answer = response.text
    answer = markdown.markdown(response.text)  # Convert markdown to HTML

    # Add emojis to the chatbot's response
    answer_with_emojis = emoji.emojize(answer)

    # Fetch the current chat
    current_chat = collection.find_one({"_id": ObjectId(chat_id)})

    # Update the title with the first 20 characters of the question if it's the first message
    if current_chat and len(current_chat["messages"]) == 0:
        title = " ".join(question.split()[:20])  # Use the first 20 words of the question as the title
    else:
        title = current_chat["title"]

    collection.update_one(
        {"_id": ObjectId(chat_id)},
        {"$push": {"messages": {"question": question, "answer": answer_with_emojis, "timestamp": datetime.now()}},
         "$set": {
             "title": title
         }
         }
    )
    return RedirectResponse(f"/chat/{chat_id}", status_code=302)

# Send sticker to specific chat
@app.post("/chat/{chat_id}/sticker", response_class=HTMLResponse)
def send_sticker(request: Request, chat_id: str, sticker_url: str = Form(...)):
    # Fetch the current chat
    current_chat = collection.find_one({"_id": ObjectId(chat_id)})

    # Update the title with a default sticker title if it's the first message
    if current_chat and len(current_chat["messages"]) == 0:
        title = "Sticker Message"
    else:
        title = current_chat["title"]

    collection.update_one(
        {"_id": ObjectId(chat_id)},
        {"$push": {"messages": {"sticker": sticker_url, "timestamp": datetime.now()}},
         "$set": {
             "title": title
         }
         }
    )
    return RedirectResponse(f"/chat/{chat_id}", status_code=302)

# React to a specific message
@app.post("/chat/{chat_id}/message/{message_id}/react", response_class=HTMLResponse)
def react_to_message(chat_id: str, message_id: str, reaction: str = Form(...)):
    collection.update_one(
        {"_id": ObjectId(chat_id), "messages._id": ObjectId(message_id)},
        {"$push": {"messages.$.reactions": reaction}}
    )
    return RedirectResponse(f"/chat/{chat_id}", status_code=302)

# Upload a file
@app.post("/upload", response_class=HTMLResponse)
async def upload_file(file: UploadFile = File(...)):
    contents = await file.read()
    # Process the file (e.g., save it or analyze it)
    return {"filename": file.filename}