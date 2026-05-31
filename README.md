# ROTA AGENT Airport AI Navigation Assistant
Rota Agent is a bilingual AI-powered airport navigation chatbot built for King Khalid International Airport (KKIA). It enables passengers to locate nearby venues, services, and facilities inside the terminal using natural language queries in both Arabic and English — without the need for static maps or staff assistance. The system uses a three-step LLM pipeline powered by GPT-4o-mini to classify user intent, identify the relevant venue category, and return proximity-ranked results based on pre-stored (X, Y) coordinates. Responses are delivered within approximately 8 seconds through a modern bilingual web interface.

```
Features
-• Bilingual Support — handles Arabic and English queries natively in a single model pipeline
-• AI-Powered Intent Classification — three-step GPT-4o-mini pipeline for category, subcategory, and brand resolution
-• Proximity-Ranked Results — venues sorted by Euclidean distance from airport origin coordinates
-• Interactive Map — visual terminal map accessible from the chat interface 
-• Smart Response Strategy — returns closest-only, all-options, or recommendation sets based on query type 
-• Dark / Light Mode — user-controlled theme toggle • Font Size Control — S / M / L size options for accessibility 
-• Fast Responses — end-to-end query resolution in ~8 seconds
```

