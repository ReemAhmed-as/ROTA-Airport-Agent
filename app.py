import os
import math
import json
import re
import requests
import pandas as pd
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv


load_dotenv()
app = Flask(__name__)

# =========================================================
# CONFIG
# =========================================================
DATA_FILE_PATH = "Final_h_updated.xlsx"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL_NAME = "openai/gpt-oss-120b:free"

# =========================================================
# SYSTEM PROMPTS
# =========================================================

# --- Intent Analyzer System Prompt ---
# This is your carefully crafted prompt — kept exactly as written.
INTENT_SYSTEM = """
You are an advanced conversational Airport Navigation AI Agent.

Your job is to understand the user's intent, conversation history, references to previous results, filtering requests, sorting requests, and follow-up questions.

You are NOT a normal chatbot.
You are an intent extraction engine.

==================================================
CORE BEHAVIOR
==================================================

You must:

1. Understand whether the user is:
   - asking a NEW search
   - referring to PREVIOUS results
   - requesting FILTERING
   - requesting SORTING
   - requesting ALTERNATIVES
   - asking FOLLOW-UP questions





2. Understand references naturally:
   Examples:
   - "غيرهم"
   - "مين منهم"
   - "الأقرب"
   - "الأرخص"
   - "which one"
   - "those"
   - "them"
   - "another"
   - "something else"

3. Use conversation context intelligently.

4. Never repeat previous suggestions if user asks for alternatives.

5. Understand semantic meaning:
   Examples:
   - "chicken"
   - "vegan"
   - "dessert"
   - "quiet place"
   - "luxury"
   - "cheap"
   - "fast food"
   - "family"
   - "romantic"
   - "coffee"

6. Return STRICT VALID JSON ONLY.

==================================================
IMPORTANT RULES
==================================================

- NEVER return explanations.
- NEVER return markdown.
- NEVER return text outside JSON.
- NEVER ignore previous conversation context.
- NEVER hallucinate unavailable fields.
- ALWAYS infer intent from history.
- ALWAYS detect follow-up references.
- Do NOT invent information.
- Do NOT assume unavailable details.
- If information is missing, say:
  "This information is not available in the airport database."
- Keep answers concise and factual.
- Use ONLY the supplied context.

==================================================
AVAILABLE INTENTS
==================================================

Use ONLY one of these intents:

- "new_search"
- "filter_previous_results"
- "sort_previous_results"
- "exclude_previous_results"
- "followup_question"

==================================================
JSON FORMAT
==================================================

Return ONLY this JSON structure:

{
  "intent": "",
  "use_previous_results": false,
  "filters": [],
  "sort_by": "",
  "sort_order": "asc",
  "exclude_previous": false,
  "reasoning": ""
}

==================================================
FIELD RULES
==================================================

intent:
- Must contain one valid intent

use_previous_results:
- true if user refers to previous results

filters:
- array of filters
- each filter MUST be object format:

[
  {
    "field": "semantic",
    "value": "chicken"
  }
]

sort_by:
Allowed values:
- ""
- "distance"
- "price"
- "rating"

sort_order:
Allowed values:
- "asc"
- "desc"

exclude_previous:
- true only if user asks for alternatives/new options

reasoning:
- short explanation of detected intent

==================================================
EXAMPLES
==================================================

USER:
"show restaurants"

OUTPUT:
{
  "intent": "new_search",
  "use_previous_results": false,
  "filters": [],
  "sort_by": "",
  "sort_order": "asc",
  "exclude_previous": false,
  "reasoning": "User started a new restaurant search"
}

--------------------------------------------------

USER:
"which one has chicken?"

OUTPUT:
{
  "intent": "filter_previous_results",
  "use_previous_results": true,
  "filters": [
    {
      "field": "semantic",
      "value": "chicken"
    }
  ],
  "sort_by": "",
  "sort_order": "asc",
  "exclude_previous": false,
  "reasoning": "User filters previous results by chicken"
}

--------------------------------------------------

USER:
"غيرهم"

OUTPUT:
{
  "intent": "exclude_previous_results",
  "use_previous_results": true,
  "filters": [],
  "sort_by": "",
  "sort_order": "asc",
  "exclude_previous": true,
  "reasoning": "User wants different options"
}

--------------------------------------------------

USER:
"الأرخص"

OUTPUT:
{
  "intent": "sort_previous_results",
  "use_previous_results": true,
  "filters": [],
  "sort_by": "price",
  "sort_order": "asc",
  "exclude_previous": false,
  "reasoning": "User wants cheapest previous option"
}

--------------------------------------------------

USER:
"best rated"

OUTPUT:
{
  "intent": "sort_previous_results",
  "use_previous_results": true,
  "filters": [],
  "sort_by": "rating",
  "sort_order": "desc",
  "exclude_previous": false,
  "reasoning": "User wants highest rated options"
}

--------------------------------------------------

USER:
"quiet coffee shops"

OUTPUT:
{
  "intent": "new_search",
  "use_previous_results": false,
  "filters": [
    {
      "field": "semantic",
      "value": "quiet"
    },
    {
      "field": "semantic",
      "value": "coffee"
    }
  ],
  "sort_by": "",
  "sort_order": "asc",
  "exclude_previous": false,
  "reasoning": "User searches for quiet coffee shops"
}

==================================================
FINAL RULE
==================================================

Return VALID JSON ONLY.
DO NOT add explanations outside JSON.
"""

# --- General Airport Agent Persona ---
# Used by category, subcategory, and brand selection steps.
AGENT_SYSTEM = """
You are a STRICT Airport Navigation AI Assistant.
- Always return valid JSON only — no prose, no markdown fences.
- Understand full conversation context from the history provided.
- Support both Arabic and English inputs equally.
"""

# =========================================================
# GLOBAL DATA & SESSION STORE
# =========================================================
DATA_LIST = []

# In-memory sessions keyed by session_id sent from the frontend.
# Each session holds:
#   history            — list of past turns (up to 15)
#   active_results     — last working dataset (for filter/sort/exclude)
#   active_category    — last resolved category string
#   active_subcategory — last resolved subcategory string
USER_SESSIONS = {}

# =========================================================
# DATA LOADING
# =========================================================
def load_data():
    global DATA_LIST
    df = pd.read_excel(DATA_FILE_PATH)
    df.columns = df.columns.str.strip().str.upper().str.replace('-', '_', regex=False)

    fill_cols = ['TRADE_CATEGORY', 'CONTENT_CATEGORY', 'TRADE_SUBCATEGORY', 'CONTENT_SUB']
    df[[c for c in fill_cols if c in df.columns]] = df[[c for c in fill_cols if c in df.columns]].ffill()

    def safe_str(val):
        return str(val).strip() if pd.notna(val) else ""

    DATA_LIST = [{
        "category":            safe_str(row.get("TRADE_CATEGORY")),
        "subcategory":         safe_str(row.get("TRADE_SUBCATEGORY")),
        "brand":               safe_str(row.get("BRAND_NAME")),
        "brand_content":       safe_str(row.get("CONTENT_BRAND")),
        "content_category":    safe_str(row.get("CONTENT_CATEGORY")),
        "content_subcategory": safe_str(row.get("CONTENT_SUB")),
        "price":               safe_str(row.get("PRICE")),
        "rating":              safe_str(row.get("RATING")),
        "x": float(row.get("X")) if pd.notna(row.get("X")) else 0.0,
        "y": float(row.get("Y")) if pd.notna(row.get("Y")) else 0.0
    } for _, row in df.iterrows()]

try:
    load_data()
except Exception as e:
    print(f"Warning: Failed to load data. {e}")

# =========================================================
# UTILITY HELPERS
# =========================================================
def is_arabic(text):
    return bool(re.search(r'[\u0600-\u06FF]', text))

def calculate_distance(x, y):
    return math.sqrt(x ** 2 + y ** 2)

def safe_numeric(value):
    """Extract first number from a string — used for price/rating sorting."""
    try:
        nums = re.findall(r'\d+\.?\d*', str(value))
        return float(nums[0]) if nums else 999999
    except Exception:
        return 999999

# =========================================================
# LLM CALLER
# Accepts a proper role/content messages list so that real
# conversation history reaches the model on every call.
# =========================================================
def call_llm(system_prompt, messages):
    """
    system_prompt : str  — task-specific instruction
    messages      : list of {"role": ..., "content": ...} dicts,
                    with the current user turn at the end
    """
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "system", "content": system_prompt}] + messages,
        "temperature": 0.2
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        result = response.json()
        if "choices" in result:
            answer = result["choices"][0]["message"]["content"].strip()
            answer = re.sub(r"^```json\s*", "", answer)
            answer = re.sub(r"^```\s*", "", answer)
            answer = re.sub(r"\s*```$", "", answer)
            return json.loads(answer)
    except Exception as e:
        print("LLM ERROR:", e)
    return None

# =========================================================
# HISTORY → MESSAGES BUILDER
# Converts stored session turns into the role/content format
# the OpenRouter chat API expects, so the model sees a real
# dialogue — not just a plain-text summary.
# =========================================================
def build_messages(history, user_input):
    """
    history    : list of past turn dicts from the session
    user_input : the current raw user message (string)
    Returns    : list of role/content dicts, current turn last
    """
    messages = []

    for turn in history[-6:]:   # last 6 turns to stay within context limits
        messages.append({
            "role": "user",
            "content": turn.get("user", "")
        })
        brands_str = ", ".join(turn.get("brands", [])) or "—"
        messages.append({
            "role": "assistant",
            "content": (
                f"I showed results in subcategory '{turn.get('subcategory', '')}' "
                f"(category: '{turn.get('category', '')}').\n"
                f"Brands displayed: {brands_str}.\n"
                f"My reply: {turn.get('message', '')}"
            )
        })

    messages.append({"role": "user", "content": user_input})
    return messages

# =========================================================
# INTENT ANALYZER
# Uses your full INTENT_SYSTEM prompt with examples.
# Returns a structured dict that drives all routing logic.
# =========================================================
def analyze_intent(user_input, history):
    """
    Returns:
      intent               — one of the 5 defined intent strings
      use_previous_results — bool
      filters              — list of {"field": str, "value": str}
      sort_by              — 'distance' | 'price' | 'rating' | ''
      sort_order           — 'asc' | 'desc'
      exclude_previous     — bool
      reasoning            — short explanation (debug only)
    """
    messages = build_messages(history, user_input)
    res = call_llm(INTENT_SYSTEM, messages)

    print(f"DEBUG intent: {res}")

    # Safe defaults — treat as fresh search if the LLM fails
    if not res or not isinstance(res, dict):
        return {
            "intent":               "new_search",
            "use_previous_results": False,
            "filters":              [],
            "sort_by":              "",
            "sort_order":           "asc",
            "exclude_previous":     False,
            "reasoning":            "fallback — LLM returned nothing"
        }

    return res

# =========================================================
# STEP 1 — CATEGORY
# Original logic preserved. Now passes full message history
# to the LLM instead of a plain string.
# =========================================================
def step_1_get_category(user_input, history, is_ar):
    unique_categories = {
        item['category']: item['content_category']
        for item in DATA_LIST if item['category']
    }
    context = "\n".join([
        f"- Category: '{c}' | Content-Category: {desc}"
        for c, desc in unique_categories.items()
    ])

    prompt = AGENT_SYSTEM + (
        f"\nالفئات:\n{context}\n"
        "اختر الفئة الأنسب بناءً على السياق الكامل.\n"
        'أعد JSON فقط: { "category": "Name" }'
        if is_ar else
        f"\nCategories:\n{context}\n"
        "Select the most appropriate category based on the full context.\n"
        'Return valid JSON: { "category": "Name" }'
    )

    messages = build_messages(history, user_input)
    res = call_llm(prompt, messages)
    selected = res.get("category", "").strip() if res else ""
    return next(
        (c for c in unique_categories if c.lower() == selected.lower()),
        list(unique_categories.keys())[0] if unique_categories else ""
    )

# =========================================================
# STEP 2 — SUBCATEGORY
# Original logic preserved. Full history passed to LLM.
# =========================================================
def step_2_get_subcategory(user_input, selected_cat, history, is_ar):
    unique_subs = {
        i['subcategory']: i['content_subcategory']
        for i in DATA_LIST
        if i['category'] == selected_cat and i['subcategory']
    }
    context = "\n".join([
        f"- Subcategory: '{sc}' | Content-Sub: {desc}"
        for sc, desc in unique_subs.items()
    ])

    prompt = AGENT_SYSTEM + (
        f"\nالطلب ضمن '{selected_cat}'.\nالفئات الفرعية:\n{context}\n"
        "القواعد: طعام=Restaurant, قهوة/حلويات=Coffee Shop, كتب/هدايا=Retail, أدوية=Pharmacy, سيارات=Transport.\n"
        'أعد JSON فقط: { "subcategory": "Name" }'
        if is_ar else
        f"\nRequest is within '{selected_cat}'.\nSubcategories:\n{context}\n"
        "Rules: Food=Restaurant, Coffee/Sweets=Coffee Shop, Books/Gifts=Retail, Medicine=Pharmacy, Cars=Transport.\n"
        'Return JSON: { "subcategory": "Name" }'
    )

    messages = build_messages(history, user_input)
    res = call_llm(prompt, messages)
    selected = res.get("subcategory", "").strip() if res else ""
    return next(
        (sc for sc in unique_subs if sc.lower() == selected.lower()),
        list(unique_subs.keys())[0] if unique_subs else ""
    )

# =========================================================
# STEP 3 — BRAND SELECTION
# Original logic preserved exactly.
# Full history passed to LLM so it respects conversation
# context (e.g. "not that one", specific brand name asked).
# =========================================================
def step_3_get_brands(user_input, selected_subcat, history, is_ar):
    brands_in_sub = [i for i in DATA_LIST if i['subcategory'] == selected_subcat and i['brand']]
    unique_brands  = {b['brand']: b for b in brands_in_sub}

    context = "\n".join([
        f"- Brand: '{b['brand']}' | Content: {b['brand_content']} | Price: {b['price']} | Rating: {b['rating']}"
        for b in unique_brands.values()
    ])

    prompt = AGENT_SYSTEM + (
        f"\nالفئة '{selected_subcat}'. المتاح:\n{context}\n"
        "إذا طلب المستخدم مكاناً محدداً بالاسم، أرجع هذا المكان فقط. "
        "إذا كان الطلب عاماً، اختر مجموعة. (لا تقل غير موجود).\n"
        'JSON: { "brands": ["B1"], "reply": "Message" }'
        if is_ar else
        f"\nSubcategory '{selected_subcat}'. Available:\n{context}\n"
        "If the user asks for a specific place by name, return ONLY that place. "
        "Otherwise, return a broad selection.\n"
        'JSON: { "brands": ["B1"], "reply": "Message" }'
    )

    messages = build_messages(history, user_input)
    res = call_llm(prompt, messages)

    print("DEBUG step_3 res:", res)

    if res:
        target_names = [b.lower().strip() for b in res.get("brands", [])]
        selected = [
            b for b in brands_in_sub
            if any(t in b['brand'].lower() or b['brand'].lower() in t for t in target_names if t)
        ]
        return selected or brands_in_sub, res.get("reply", "")

    return brands_in_sub, (
        "إليك بعض الخيارات المتاحة في هذه الفئة:" if is_ar
        else "Here are some convenient options in this category:"
    )

# =========================================================
# SEMANTIC FILTER ENGINE
# Handles {"field": "semantic", "value": "..."} filters from
# the intent analyzer by scoring each brand against the
# keyword across all text fields.
# Also handles explicit field filters as a fallback.
# =========================================================
def apply_filters(data, filters):
    if not filters:
        return data

    filtered = data
    for f in filters:
        field = str(f.get("field", "")).lower().strip()
        value = str(f.get("value", "")).lower().strip()
        if not value:
            continue

        temp = []
        for item in filtered:
            # Build a single searchable string from all text fields
            searchable = " ".join([
                item.get("brand", ""),
                item.get("brand_content", ""),
                item.get("subcategory", ""),
                item.get("content_subcategory", ""),
                item.get("price", ""),
                item.get("rating", "")
            ]).lower()

            if value in searchable:
                temp.append(item)

        # Only apply the filter if it actually narrows results
        if temp:
            filtered = temp

    return filtered

# =========================================================
# SORT ENGINE
# Sorts the working dataset by distance, price, or rating.
# =========================================================
def apply_sort(data, sort_by, order):
    if not sort_by:
        return data

    reverse = (order == "desc")

    if sort_by == "distance":
        data.sort(key=lambda x: calculate_distance(x['x'], x['y']), reverse=reverse)
    elif sort_by == "price":
        data.sort(key=lambda x: safe_numeric(x['price']), reverse=reverse)
    elif sort_by == "rating":
        data.sort(key=lambda x: safe_numeric(x['rating']), reverse=reverse)

    return data

# =========================================================
# FINAL BRANDS BUILDER
# This is the ORIGINAL display logic — completely untouched.
# Handles: distance sort, restroom/gate special case,
# Closest + Recommendation labels, max-4 cap.
# Extracted into its own function for cleanliness only.
# =========================================================
def build_final_brands(selected_instances, selected_subcat, is_ar):
    if not selected_instances:
        return [], ""

    for b in selected_instances:
        b['distance'] = calculate_distance(b['x'], b['y'])

    selected_instances.sort(key=lambda loc: loc['distance'])

    v_subcat = selected_subcat.lower()
    is_restroom = any(
        kw in b['brand'].lower()
        for b in selected_instances
        for kw in ('bathroom', 'restroom', 'toilet', 'wc')
    )
    is_gate = (
        'gate' in v_subcat or 'بواب' in v_subcat or
        any('gate' in b['brand'].lower() or 'بواب' in b['brand'].lower()
            for b in selected_instances)
    )

    final_brands = []

    # --- Restrooms & Gates: show ALL sorted by distance ---
    if is_restroom or is_gate:
        for loc in selected_instances:
            final_brands.append({
                "name":        loc['brand'],
                "content":     loc['brand_content'],
                "distance":    round(loc['distance'], 2),
                "coordinates": f"({loc['x']}, {loc['y']})",
                "x":           loc['x'],
                "y":           loc['y'],
                "type":        "regular",
                "price":       loc['price']
            })
        msg_ext = (
            "إليك جميع الخيارات المتاحة، مرتبة حسب الأقرب لك:"
            if is_ar else
            "Here are all available options, sorted by closest to you:"
        )
        return final_brands, msg_ext

    # --- Normal places: Closest + up to 3 Recommendations ---
    unique_selected  = set(b['brand'] for b in selected_instances)
    is_public_place  = 'public facilities' in v_subcat
    closest          = selected_instances[0]

    if is_public_place or len(unique_selected) > 1:
        final_brands.append({
            "name":        closest['brand'] + (" (الأقرب)" if is_ar else " (Closest)"),
            "content":     closest['brand_content'],
            "distance":    round(closest['distance'], 2),
            "coordinates": f"({closest['x']}, {closest['y']})",
            "x":           closest['x'],
            "y":           closest['y'],
            "type":        "closest",
            "price":       closest['price']
        })
        added = {closest['brand']}
        for loc in selected_instances[1:]:
            if is_public_place or loc['brand'] not in added:
                added.add(loc['brand'])
                final_brands.append({
                    "name":        loc['brand'] + (" (توصية)" if is_ar else " (Recommendation)"),
                    "content":     loc['brand_content'],
                    "distance":    round(loc['distance'], 2),
                    "coordinates": f"({loc['x']}, {loc['y']})",
                    "x":           loc['x'],
                    "y":           loc['y'],
                    "type":        "recommendation",
                    "price":       loc['price']
                })
                if len(final_brands) >= 4:
                    break
        msg_ext = (
            "لقد وجدنا أقرب خيار لك، بالإضافة إلى بعض التوصيات:"
            if is_ar else
            "We found the closest option for you, along with some recommendations:"
        )
    else:
        final_brands.append({
            "name":        closest['brand'],
            "content":     closest['brand_content'],
            "distance":    round(closest['distance'], 2),
            "coordinates": f"({closest['x']}, {closest['y']})",
            "x":           closest['x'],
            "y":           closest['y'],
            "type":        "closest",
            "price":       closest['price']
        })
        msg_ext = (
            "لقد وجدنا أقرب موقع لك بناءً على إحداثياتك:"
            if is_ar else
            "We found the closest location based on your coordinates:"
        )

    return final_brands, msg_ext

# =========================================================
# MAIN PROCESS QUERY
# =========================================================
def process_query(user_input, session_data):
    """
    Stateful pipeline:
      A. analyze_intent   → understand what the user wants
      B. route            → reuse active_results OR run fresh 3-step pipeline
      C. exclude          → remove previously shown brands (alternatives)
      D. apply_filters    → semantic keyword filtering
      E. apply_sort       → distance / price / rating
      F. handle_followup  → text answers for followup questions
      G. build_final_brands → original display logic (untouched)
      H. compose message
      I. persist active_results for next turn
    """
    history = session_data["history"]
    is_ar = is_arabic(user_input)

    # ----------------------------------------------------------
    # A — What does the user want this turn?
    # ----------------------------------------------------------
    analysis = analyze_intent(user_input, history)
    intent = analysis.get("intent", "new_search")
    use_previous = analysis.get("use_previous_results", False)
    filters = analysis.get("filters", [])
    sort_by = analysis.get("sort_by", "")
    sort_order = analysis.get("sort_order", "asc")
    exclude_prev = analysis.get("exclude_previous", False)

    # ----------------------------------------------------------
    # B — Get working dataset
    # ----------------------------------------------------------
    if exclude_prev and session_data["active_subcategory"]:
        # ALTERNATIVES MODE:
        # Go back to the FULL subcategory pool from DATA_LIST,
        # not active_results — otherwise there's nothing left to exclude from.
        selected_cat = session_data["active_category"]
        selected_subcat = session_data["active_subcategory"]
        full_pool = [i for i in DATA_LIST if i['subcategory'] == selected_subcat and i['brand']]
        working_data = full_pool

    elif use_previous and session_data["active_results"]:
        # FILTER / SORT MODE: operate on the previous result set
        working_data = list(session_data["active_results"])  # shallow copy
        selected_cat = session_data["active_category"]
        selected_subcat = session_data["active_subcategory"]

    else:
        # FRESH SEARCH: run full category → subcategory → brands pipeline
        selected_cat = step_1_get_category(user_input, history, is_ar)
        selected_subcat = step_2_get_subcategory(user_input, selected_cat, history, is_ar)
        raw_instances, _ = step_3_get_brands(user_input, selected_subcat, history, is_ar)
        working_data = raw_instances

        session_data["active_category"] = selected_cat
        session_data["active_subcategory"] = selected_subcat

    # ----------------------------------------------------------
    # C — Exclude previously shown brands (alternatives mode)
    # ----------------------------------------------------------
    if exclude_prev and session_data["active_results"]:
        # Collect ALL brand names ever shown across the whole history
        # for this subcategory — not just the last turn.
        ever_shown = set()
        for turn in session_data["history"]:
            if turn.get("subcategory") == selected_subcat:
                for b in turn.get("brands", []):
                    ever_shown.add(b.lower())

        temp = [x for x in working_data if x["brand"].lower() not in ever_shown]
        if temp:
            working_data = temp
        # If everything was shown already, reset and show all (avoid empty result)
        else:
            working_data = [i for i in DATA_LIST if i['subcategory'] == selected_subcat and i['brand']]

    # ----------------------------------------------------------
    # D — Apply semantic / keyword filters
    # ----------------------------------------------------------
    working_data = apply_filters(working_data, filters)

    # ----------------------------------------------------------
    # E — Apply sort (distance / price / rating)
    # ----------------------------------------------------------
    working_data = apply_sort(working_data, sort_by, sort_order)

    # ----------------------------------------------------------
    # F — Handle followup questions differently (text reply, not cards)
    # ----------------------------------------------------------
    if intent == "followup_question":
        # Call the dedicated followup handler
        text_reply, kept_brands = handle_followup(user_input, session_data, history, is_ar)

        return {
            "subcategory": selected_subcat,
            "brands": kept_brands,  # Keep previous cards visible
            "message": text_reply,  # Text answer to user's question
            "is_followup": True  # Optional: let frontend know it's a text reply
        }

    # ----------------------------------------------------------
    # G — Build final brands list (original display logic) for non-followup intents
    # ----------------------------------------------------------
    final_brands, msg_ext = build_final_brands(working_data, selected_subcat, is_ar)

    # ----------------------------------------------------------
    # H — Compose the reply message based on detected intent
    # ----------------------------------------------------------
    if intent == "exclude_previous_results":
        base_msg = (
            "إليك خيارات مختلفة بناءً على طلبك."
            if is_ar else
            "Here are different options based on your request."
        )
    elif intent == "filter_previous_results":
        base_msg = (
            "لقد قمنا بتصفية النتائج السابقة بناءً على طلبك."
            if is_ar else
            "We filtered the previous results based on your request."
        )
    elif intent == "sort_previous_results":
        base_msg = (
            "لقد قمنا بترتيب النتائج السابقة."
            if is_ar else
            "We sorted the previous results."
        )
    else:
        base_msg = (
            "لقد وجدنا أفضل النتائج لك."
            if is_ar else
            "We found the best matching results for you."
        )

    message = f"{base_msg}\n\n{msg_ext}" if msg_ext else base_msg

    # ----------------------------------------------------------
    # I — Persist active results so next turn can operate on them
    # ----------------------------------------------------------
    session_data["active_results"] = working_data

    # Return — same structure the frontend already expects
    return {
        "subcategory": selected_subcat,
        "brands": final_brands,
        "message": message
    }

def handle_followup(user_input, session_data, history, is_ar):
    """
    Returns (message: str, brands: list)
    - message : a direct natural-language answer to the question
    - brands  : the same cards from the previous turn (unchanged)
    """
    active = session_data.get("active_results", [])
    shown_names = set()
    for turn in history:
        for b in turn.get("brands", []):
            shown_names.add(b.lower())

    # Find the brands that are relevant — prefer ones mentioned by name in the question
    q_lower = user_input.lower()
    relevant = [
        b for b in active
        if b["brand"].lower() in q_lower or b["brand"].lower() in shown_names
    ]
    if not relevant:
        relevant = active  # fall back to all active results

    # Deduplicate by brand name
    seen = set()
    unique_relevant = []
    for b in relevant:
        if b["brand"] not in seen:
            seen.add(b["brand"])
            unique_relevant.append(b)

    # Build a context block from available data fields
    brand_context = "\n\n".join([
        f"Brand: {b['brand']}\n"
        f"Description: {b['brand_content']}\n"
        f"Price range: {b['price']}\n"
        f"Rating: {b['rating']}\n"
        f"Location: ({b['x']}, {b['y']})\n"
        f"Distance: {round(calculate_distance(b['x'], b['y']), 2)} units"
        for b in unique_relevant
    ])

    prompt = AGENT_SYSTEM + (
        f"""
أنت مساعد مطار. المستخدم يسأل سؤالاً متابعاً عن المطاعم/المحلات التالية:

{brand_context}

أجب على سؤال المستخدم مباشرةً بشكل طبيعي ومفيد باللغة العربية.
لا ترجع JSON. فقط اكتب إجابة واضحة ومباشرة.
إذا المعلومة غير موجودة في البيانات، قل ذلك بأدب.
"""
        if is_ar else
        f"""
You are an airport assistant. The user is asking a follow-up question about these places:

{brand_context}

Answer the user's question directly in natural, helpful English.
Do NOT return JSON. Write a clear, direct answer.
If the information is not available in the data, say so politely.
"""
    )

    # For followup we send a single user message — no JSON parsing needed
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    messages = build_messages(history, user_input)
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "system", "content": prompt}] + messages,
        "temperature": 0.4
    }

    text_reply = ""
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        result = response.json()
        if "choices" in result:
            text_reply = result["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print("FOLLOWUP LLM ERROR:", e)

    if not text_reply:
        text_reply = (
            "عذراً، لم أتمكن من الإجابة على سؤالك. يرجى المحاولة مجدداً."
            if is_ar else
            "Sorry, I couldn't answer your question. Please try again."
        )

    # Rebuild the same brand cards from the previous turn so they stay visible
    prev_brand_names = set()
    if history:
        for b in history[-1].get("brands", []):
            prev_brand_names.add(b.lower())

    shown_cards = []
    seen_cards  = set()
    for b in active:
        if b["brand"].lower() in prev_brand_names and b["brand"] not in seen_cards:
            seen_cards.add(b["brand"])
            dist = calculate_distance(b["x"], b["y"])
            shown_cards.append({
                "name":        b["brand"],
                "content":     b["brand_content"],
                "distance":    round(dist, 2),
                "coordinates": f"({b['x']}, {b['y']})",
                "x":           b["x"],
                "y":           b["y"],
                "type":        "recommendation",
                "price":       b["price"]
            })

    return text_reply, shown_cards

# =========================================================
# ROUTES
# =========================================================
@app.route('/')
def home():
    return render_template('welcome.html')

@app.route('/chat')
def chat():
    return render_template('index.html')

@app.route('/map')
def show_map():
    return render_template('map.html')

@app.route('/api/locations')
def api_locations():
    return jsonify(DATA_LIST)

@app.route('/ask', methods=['POST'])
def ask():
    req        = request.get_json()
    user_input = req.get("message", "")
    session_id = req.get("session_id", "default")  # frontend sends this per user

    if not user_input:
        return jsonify({"message": "يرجى كتابة رسالة. / Please enter a message."})

    # Create session bucket on first visit
    if session_id not in USER_SESSIONS:
        USER_SESSIONS[session_id] = {
            "history":            [],
            "active_results":     [],
            "active_category":    "",
            "active_subcategory": ""
        }

    session_data = USER_SESSIONS[session_id]

    # Run the full pipeline
    result = process_query(user_input, session_data)

    # Save this turn — strip display suffixes from brand names before storing
    clean_brand_names = [
        r["name"]
        .replace(" (Closest)", "").replace(" (Recommendation)", "")
        .replace(" (الأقرب)", "").replace(" (توصية)", "")
        for r in result["brands"]
    ]
    session_data["history"].append({
        "user":        user_input,
        "response":    result["message"],
        "brands":      clean_brand_names,
        "category":    session_data.get("active_category", ""),
        "subcategory": result["subcategory"]
    })
    session_data["history"] = session_data["history"][-15:]  # keep last 15 turns

    return jsonify(result)

@app.route('/reset', methods=['POST'])
def reset_session():
    """Let the frontend offer a 'New Conversation' button."""
    req        = request.get_json() or {}
    session_id = req.get("session_id", "default")
    if session_id in USER_SESSIONS:
        del USER_SESSIONS[session_id]
    return jsonify({"status": "ok"})

# =========================================================
# RUN
# =========================================================
if __name__ == '__main__':
    app.run(debug=True, port=8000)
