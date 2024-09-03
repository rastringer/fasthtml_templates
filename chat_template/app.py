from fasthtml.common import *
import requests
import base64
import vertexai
from vertexai.generative_models import GenerativeModel, Part
import vertexai.preview.generative_models as generative_models
import json

# Load configuration from a JSON file
with open('config.json') as f:
    config = json.load(f)

# Set up the app, including daisyui and tailwind for the chat component
tlink = Script(src="https://cdn.tailwindcss.com")
dlink = Link(rel="stylesheet", href="https://cdn.jsdelivr.net/npm/daisyui@4.11.1/dist/full.min.css")
app = FastHTML(hdrs=(tlink, dlink, picolink))

# Gemini configuration
vertexai.init(project=config['project_id'], location=config['location'])
model = GenerativeModel(config['model_name'])
chat = model.start_chat(history=[])
messages = []

# Simple card component
def Card(title, content, image_url=None):
    card_content = [
        Div(H2(title, cls="card-title"), P(content), cls="card-body")
    ]
    if image_url:
        card_content.insert(0, Img(src=image_url, alt=title, cls="w-full object-cover h-64"))
    return Div(*card_content, cls="card bg-base-100 shadow-xl")

# Chat message component, polling if message is still being generated
def ChatMessage(msg_idx):
    msg = messages[msg_idx]
    text = "..." if msg['content'] == "" else msg['content']
    bubble_class = f"chat-bubble-{'primary' if msg['role'] == 'user' else 'secondary'}"
    chat_class = f"chat-{'end' if msg['role'] == 'user' else 'start'}"
    generating = 'generating' in messages[msg_idx] and messages[msg_idx]['generating']
    stream_args = {"hx_trigger":"every 0.1s", "hx_swap":"outerHTML", "hx_get":f"/chat_message/{msg_idx}"}
    return Div(Div(msg['role'], cls="chat-header"),
               Div(text, cls=f"chat-bubble {bubble_class}"),
               cls=f"chat {chat_class}", id=f"chat-message-{msg_idx}", 
               **stream_args if generating else {})

# The input field for the user message
def ChatInput():
    return Input(type="text", name='msg', id='msg-input', 
                 placeholder="Type a message", 
                 cls="input input-bordered w-full", hx_swap_oob='true')

# The main screen
@app.route("/")
def get():
    messages = []
    page = Body(
        Div(
            Img(src=config['logo_url'], alt="Company Logo", cls="w-32 mx-auto mb-2"),
            H1(config['app_name'], cls="text-2xl font-bold text-center mb-2"),
            Card(config['welcome_title'], config['welcome_message'], config['welcome_image'],
                ),
            Div(*[ChatMessage(idx) for idx in range(len(messages))],
                id="chatlist", cls="chat-box h-[30vh] overflow-y-auto mb-4"),
            Form(Group(ChatInput(), Button("Send", cls="btn btn-primary")),
                hx_post="/", hx_target="#chatlist", hx_swap="beforeend",
                cls="flex space-x-2 mt-2",
            ),
            cls="p-4 max-w-lg mx-auto"
        )
    )
    return Title(config['app_name']), page 

# Run the chat model in a separate thread
@threaded
def get_response(r, idx):
    for chunk in r: messages[idx]["content"] += chunk
    messages[idx]["generating"] = False

def query_gemini(message):
    response = chat.send_message(message)
    return response.text

# Handle the form submission
@app.post("/")
def post(msg:str):
    idx = len(messages)
    messages.append({"role": "user", "content": msg})  
    prompt = f"{config['system_command']}\n\n{msg}"
    gemini_response = query_gemini(prompt)
    messages.append({"role": "assistant", "generating": True, "content": gemini_response})
    get_response(gemini_response, idx+1) # Start a new thread to fill in content
    return (ChatMessage(idx),  # The user's message
            ChatMessage(idx + 1),  # The chatbot's response
            ChatInput())  # Clear the input field

if __name__ == '__main__':
    import uvicorn
    uvicorn.run("app:app", host='0.0.0.0', port=8080, reload=True)