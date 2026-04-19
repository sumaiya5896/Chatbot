from fastapi import FastAPI, Request, Form, File, UploadFile, Depends
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
from starlette.middleware.sessions import SessionMiddleware
from passlib.context import CryptContext

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="your_secret_key")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Initialize Google GenAI client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Initialize MongoDB client
mongo_client = MongoClient(os.getenv("MONGO_URI"))
db = mongo_client["chat_db"]
users_collection = db["users"]
chats_collection = db["chats"]

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Helper function to get the current user
def get_current_user(request: Request):
    user_id = request.session.get("user")
    if not user_id:
        return None  # Return None if the user is not logged in
    user = users_collection.find_one({"_id": ObjectId(user_id)})
    return user

# Home page
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)  # Redirect to login if user is not logged in

    chats = list(chats_collection.find({"user_id": user["_id"]}).sort("created_at", -1).limit(20))
    return templates.TemplateResponse("index.html", {"request": request, "chats": chats, "current_chat": None, "user": user})

# Create new chat
@app.get("/new", response_class=HTMLResponse)
def new_chat(request: Request):
    user = get_current_user(request)   # ✅ FIX: use 'user'

    if not user:
        return RedirectResponse("/login", status_code=302)

    try:
        result = chats_collection.insert_one({
            "title": "New Chat",
            "created_at": datetime.now(),
            "messages": [],
            "user_id": user["_id"]   # ✅ now valid
        })

        return RedirectResponse(f"/chat/{result.inserted_id}", status_code=302)

    except Exception as e:
        print("REAL ERROR:", e)   # 👈 add this for debugging
        return HTMLResponse(content="An error occurred while creating a new chat.", status_code=500)

# Open a specific chat
@app.get("/chat/{chat_id}", response_class=HTMLResponse)
def open_chat(request: Request, chat_id: str):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)  # Redirect to login if user is not logged in

    try:
        chats = list(chats_collection.find({"user_id": user["_id"]}).sort("created_at", -1))
        current_chat = chats_collection.find_one({"_id": ObjectId(chat_id), "user_id": user["_id"]})
        if not current_chat:
            return RedirectResponse("/", status_code=302)  # Redirect to home if chat not found

        return templates.TemplateResponse("index.html", {"request": request, "chats": chats, "current_chat": current_chat, "user": user})
    except Exception as e:
        print(f"Error opening chat: {e}")
        return HTMLResponse(content="An error occurred while opening the chat.", status_code=500)

# Send message to specific chat
@app.post("/chat/{chat_id}", response_class=HTMLResponse)
def send_message(request: Request, chat_id: str, question: str = Form(...)):

    # ✅ FIX: get proper user
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    user_id = user["_id"]

    # ✅ Generate AI response
    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=question
    )

    answer = markdown.markdown(response.text)
    answer_with_emojis = emoji.emojize(answer)

    # ✅ FIX: correct query
    current_chat = chats_collection.find_one({
        "_id": ObjectId(chat_id),
        "user_id": user_id
    })

    if not current_chat:
        return RedirectResponse("/", status_code=302)

    # ✅ Title logic
    if len(current_chat["messages"]) == 0:
        clean_question = re.sub(r'<.*?>', '', question) 
        clean_question =clean_question.strip()
        title = " ".join(clean_question.split()[:6])
    else:
        title = current_chat["title"]

    # ✅ FIX: correct update structure
    chats_collection.update_one(
        {"_id": ObjectId(chat_id)},
        {
            "$push": {
                "messages": {
                    "_id": ObjectId(),
                    "question": question,
                    "answer": answer_with_emojis
                }
            },
            "$set": {"title": title}
        }
    )

    return RedirectResponse(f"/chat/{chat_id}", status_code=302)
# Send sticker to specific chat
@app.post("/chat/{chat_id}/sticker", response_class=HTMLResponse)
def send_sticker(request: Request, chat_id: str, sticker_url: str = Form(...)):
    user_id = get_current_user(request)
    if not user_id:
        return RedirectResponse("/login", status_code=302)  # Redirect to login if user is not logged in

    # Fetch the current chat
    current_chat = chats_collection.find_one({"_id": ObjectId(chat_id), "user_id": user_id})

    # Update the title with a default sticker title if it's the first message
    if current_chat and len(current_chat["messages"]) == 0:
        title = "Sticker Message"
    else:
        title = current_chat["title"]

    chats_collection.update_one(
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
    chats_collection.update_one(
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

#signup page
@app.post("/signup")
def signup(request: Request, email: str = Form(...), password: str = Form(...)):
    existing = users_collection.find_one({"email": email})
    if existing:
        return templates.TemplateResponse("index.html", {"request": request, "error": "User already exists. Please log in."})
    
    hashed_password = pwd_context.hash(password)
    users_collection.insert_one({"email": email, "password": hashed_password})
    return RedirectResponse("/login", status_code=302)

#login page
@app.get("/login", response_class=HTMLResponse)
def show_login(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...)):
    user = users_collection.find_one({"email": email})
    if not user:
        return RedirectResponse("/?error=email_not_found",status_code=302)  # Redirect to home with error query parameter
    if not pwd_context.verify(password, user["password"]):
        return RedirectResponse("/?error=incorrect_password",status_code=302)  # Redirect to home with error query parameter
    
    request.session["user"] = str(user["_id"])  # Set the user ID in the session
    return RedirectResponse("/", status_code=302)

# Logout
@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=302)






















