import json
import os
import re

import faiss
import numpy as np
from dotenv import load_dotenv
from groq import Groq
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

load_dotenv()

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
embedding_model = None
SEARCH_DISTANCE_THRESHOLD = 2.0

SYSTEM_PROMPT = """You are a friendly, helpful AI assistant for a website. You're warm and conversational, like a knowledgeable shop assistant. You help customers find products, answer questions, and place orders.

RESPONSE FORMAT - always return valid JSON:
{
  "message": "Your reply here.",
  "options": ["Button label"],
  "links": [{"label": "Text", "url": "https://..."}],
  "db_action": null
}

TONE AND STYLE:
- Be friendly and natural.
- Never start with "I", "Sure", "Of course", or filler phrases.
- Don't repeat the user's message back to them.
- Never show raw JSON, field names, or technical data in the message.

ANSWER COMPLETENESS:
- Always write the full answer in your first response.
- Never rely on buttons or links to deliver the actual answer.
- Options come after a complete answer.
- Never reply with only options or only links when the user asked a factual question.

FORMATTING:
- Use bullet lists for multiple items.
- Use numbered steps for processes.
- Use bold for product names, prices, and key terms.
- Avoid long unbroken paragraphs.

CRITICAL:
- Never include db_action JSON or field names inside the message text.
- Never write "Options:" or "Links:" inside the message text.

OPTIONS:
- Include 2-4 short follow-up buttons when useful.
- After showing products, use specific actions such as product names.
- When login is required, use exactly ["Log In", "Sign Up"].

LINKS:
- Links are follow-ups only, never a replacement for the real answer.

DB_ACTION:
- lookup_user: {"type": "lookup_user", "email": "..."}
- create_order: {"type": "create_order", "data": {"customer_id": 1, "user_id": 1, "user_email": "...", "user_name": "...", "product_id": 1, "product_name": "EXACT name from KB", "quantity": 1, "delivery_address": "..."}}
- register_user: {"type": "register_user", "data": {"name": "...", "email": "...", "phone": "...", "address": "..."}}
- get_orders: {"type": "get_orders", "user_email": "...", "customer_id": 1}

USER CONTEXT:
- is_logged_in=true means the user is authenticated.
- is_logged_in=false means you know nothing about them.

ORDERING FLOW:
0. If is_logged_in=false and user wants to order, say "You'll need to log in first." and set options to exactly ["Log In", "Sign Up"].
1. Confirm the exact product name, price, and quantity, then ask if you should place the order.
2. Show the delivery address from the logged-in user context and confirm it.
3. Summarize the order and ask for final confirmation.
4. Only after final confirmation, set db_action create_order.

ORDER HISTORY:
- When the user asks for order history, set db_action get_orders.

Always return only the JSON object. No text before or after it.
"""


class KnowledgeBase:
    def __init__(self):
        self.index = None
        self.chunks = []

    def process_pdf(self, file_path):
        reader = PdfReader(file_path)
        text = ""
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + " "
        raw = [part.strip() for part in text.split("\n\n") if part.strip()]
        self.chunks = []
        buffer = ""
        for paragraph in raw:
            if len(buffer) + len(paragraph) < 600:
                buffer += " " + paragraph
            else:
                if buffer.strip():
                    self.chunks.append(buffer.strip())
                buffer = paragraph
        if buffer.strip():
            self.chunks.append(buffer.strip())
        if self.chunks:
            self._build_index()

    def process_chunks(self, chunks: list):
        self.chunks = [chunk for chunk in chunks if chunk.strip()]
        if self.chunks:
            self._build_index()

    def add_chunks(self, new_chunks: list):
        filtered = [chunk for chunk in new_chunks if chunk.strip()]
        if filtered:
            self.chunks += filtered
            self._build_index()

    def _build_index(self):
        embeddings = get_embedding_model().encode(self.chunks)
        dim = embeddings.shape[1]
        self.index = faiss.IndexFlatL2(dim)
        self.index.add(np.array(embeddings).astype("float32"))

    def search(self, query, top_k=5):
        if not self.index or not self.chunks:
            return []
        query_vector = get_embedding_model().encode([query]).astype("float32")
        distances, indices = self.index.search(query_vector, top_k)
        return [
            self.chunks[index]
            for distance, index in zip(distances[0], indices[0])
            if index != -1 and distance < SEARCH_DISTANCE_THRESHOLD
        ]


def get_embedding_model():
    global embedding_model
    if embedding_model is None:
        embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return embedding_model


def generate_response(
    user_query: str,
    retrieved_chunks: list,
    user_info: dict = None,
    conversation_history: list = None,
    custom_rules: str = "",
    personality: str = "friendly",
) -> dict:
    personality_tones = {
        "friendly": "Be warm, approachable and encouraging. Use light, positive language.",
        "professional": "Be polite, precise and formal. Avoid casual language.",
        "casual": "Be relaxed and conversational, like texting a knowledgeable friend.",
        "concise": "Be extremely brief. One sentence answers where possible. No fluff.",
        "enthusiastic": "Be energetic and upbeat. Show genuine excitement about helping.",
    }
    tone_instruction = personality_tones.get(personality, personality_tones["friendly"])

    dynamic_additions = f"\nPERSONALITY: {tone_instruction}"
    if custom_rules:
        dynamic_additions += (
            "\n\nOWNER RULES (follow these, they override defaults where applicable):\n"
            f"{custom_rules}"
        )

    system = SYSTEM_PROMPT + dynamic_additions
    parts = []

    if user_info and (user_info.get("name") or user_info.get("email")):
        parts.append(
            "LOGGED-IN USER: "
            f"name={user_info.get('name', '')}, "
            f"email={user_info.get('email', '')}, "
            f"address={user_info.get('address', '')}, "
            f"customer_id={user_info.get('user_id', '')}, "
            f"user_id={user_info.get('user_id', '')}, "
            "is_logged_in=true"
        )

    if retrieved_chunks:
        parts.append("KNOWLEDGE BASE:\n" + "\n".join(retrieved_chunks))

    context = "\n\n".join(parts) if parts else ""
    messages = [{"role": "system", "content": system}]

    if conversation_history:
        for turn in conversation_history[-8:]:
            messages.append({"role": turn["role"], "content": turn["content"]})

    user_content = f"{context}\n\nUser message: {user_query}" if context else user_query
    messages.append({"role": "user", "content": user_content})

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            temperature=0.3,
            max_tokens=700,
        )
        raw = response.choices[0].message.content.strip()
    except Exception as exc:
        print(f"LLM error: {exc}")
        return {"message": "Sorry, I couldn't process that.", "options": [], "links": [], "db_action": None}

    def sanitise_message(message: str) -> str:
        message = re.sub(r'\{[\s"]*"?type"?\s*:\s*"[^"]*"[^}]*\}', "", message, flags=re.DOTALL)
        message = re.sub(r"\n?Options?:\s*\[.*?\]", "", message, flags=re.DOTALL | re.IGNORECASE)
        message = re.sub(r"\n?Links?:\s*\[.*?\]", "", message, flags=re.DOTALL | re.IGNORECASE)
        message = re.sub(r'\n?\["[\w][^"]*"(?:,\s*"[\w][^"]*")*\]\s*$', "", message.strip(), flags=re.DOTALL)
        return re.sub(r"\n{3,}", "\n\n", message).strip()

    parsed = None
    json_str = None
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        json_str = match.group()
        try:
            parsed = json.loads(json_str)
        except json.JSONDecodeError:
            parsed = None

    if parsed is None and json_str:
        try:
            buffer = []
            in_string = False
            for index, char in enumerate(json_str):
                if char == '"' and (index == 0 or json_str[index - 1] != "\\"):
                    in_string = not in_string
                    buffer.append(char)
                elif in_string and char == "\n":
                    buffer.append("\\n")
                elif in_string and char == "\r":
                    buffer.append("\\r")
                elif in_string and char == "\t":
                    buffer.append("\\t")
                else:
                    buffer.append(char)
            parsed = json.loads("".join(buffer))
        except Exception:
            parsed = None

    if parsed is None:
        source = json_str or raw

        def grab_value(key, default=None):
            inner_match = re.search(rf'"{key}"\s*:\s*"((?:[^"\\]|\\.)*)"', source, re.DOTALL)
            if not inner_match:
                return default
            try:
                return json.loads('"' + inner_match.group(1) + '"').replace("\\n", "\n")
            except Exception:
                return inner_match.group(1).replace("\\n", "\n")

        def grab_list(key):
            inner_match = re.search(rf'"{key}"\s*:\s*(\[[^\]]*\])', source)
            if not inner_match:
                return []
            try:
                return json.loads(inner_match.group(1))
            except Exception:
                return []

        parsed = {
            "message": grab_value("message", raw),
            "options": grab_list("options"),
            "links": grab_list("links"),
            "db_action": None,
        }
        db_action_match = re.search(r'"db_action"\s*:\s*(\{.*?\}|null)', source, re.DOTALL)
        if db_action_match and db_action_match.group(1) != "null":
            try:
                parsed["db_action"] = json.loads(db_action_match.group(1))
            except Exception:
                parsed["db_action"] = None

    message = parsed.get("message", raw)
    if isinstance(message, str) and message.strip().startswith("{"):
        inner_message = re.search(r'"message"\s*:\s*"((?:[^"\\]|\\.)*)"', message, re.DOTALL)
        if inner_message:
            message = inner_message.group(1).replace("\\n", "\n")

    return {
        "message": sanitise_message(message),
        "options": parsed.get("options", []),
        "links": parsed.get("links", []),
        "db_action": parsed.get("db_action"),
    }
