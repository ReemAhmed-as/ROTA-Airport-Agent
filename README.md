# ROTA AGENT Airport AI Navigation Assistant
Rota Agent is a bilingual AI-powered airport navigation chatbot built for King Khalid International Airport (KKIA). It enables passengers to locate nearby venues, services, and facilities inside the terminal using natural language queries in both Arabic and English — without the need for static maps or staff assistance. The system uses a three-step LLM pipeline powered by GPT-4o-mini to classify user intent, identify the relevant venue category, and return proximity-ranked results based on pre-stored (X, Y) coordinates. Responses are delivered within approximately 8 seconds through a modern bilingual web interface.


**Features**

1. Bilingual Support — handles Arabic and English queries natively in a single model pipeline
2. AI-Powered Intent Classification — three-step GPT-4o-mini pipeline for category, subcategory, and brand resolution
3. Proximity-Ranked Results — venues sorted by Euclidean distance from airport origin coordinates
4. Interactive Map — visual terminal map accessible from the chat interface 
5. Smart Response Strategy — returns closest-only, all-options, or recommendation sets based on query type 
6. Dark / Light Mode — user-controlled theme toggle
7. Font Size Control — S / M / L size options for accessibility 
8. Fast Responses — end-to-end query resolution in ~8 seconds



**Installation & Setup**
1. Clone the Repository
```
git clone https://github.com/your-username/rota-agent.git cd rota-agent
```
2. Install Dependencies
```
pip install flask pandas openpyxl requests
 ```
3. Configure API Key
```
Open app.py and replace the OpenRouter API key with your own:
OPENROUTER_API_KEY = "your-openrouter-api-key-here"
```
4. Run the Application
```
python app.py
The app will be available at: http://localhost:8000
```
How It Works
1.	User submits a query in Arabic or English via the chat interface.
2.	Language Detection — Regex checks for Arabic Unicode characters (\u0600–\u06FF).
3.	Step 1 —GPT-OSS 120B classifies the query into a top-level trade category (e.g., Food & Beverage, Transport).
4.	Step 2 — GPT-OSS 120B narrows the result to a subcategory (e.g., Restaurant, Coffee Shop, Pharmacy).
5.	Step 3 — Relevant venues are retrieved from the dataset, ranked by Euclidean distance, and filtered by intent.
6.	Response — The Flask API returns a JSON payload with venue names, distances, coordinates, and a natural-language message.

API Endpoint
POST /ask
Accepts a JSON body and returns navigation results.

Request
```
{ "message": "أين أقرب مطعم؟" }
```
Response
```
{ "subcategory": "Restaurant",
  "message": "لقد وجدنا أقرب خيار لك...",
  "brands": [
    { "name": "Munch (Closest)", "distance": 13.0,
      "coordinates": "(13, 0)", "x": 13, "y": 0,
      "type": "closest", "price": "$$" }
  ] }
```

Requirements
1. Python 3.8+
2. Flask
3. Pandas + openpyxl
4. Requests
5. OpenRouter API key (GPT-OSS 120B access)
