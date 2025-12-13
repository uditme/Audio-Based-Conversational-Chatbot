🎙️ Real-Time Voice Chat Application

A real-time voice chat system using Vosk (STT), Gemini 2.5 LLM, FastAPI, Django, and Docker.

📺 Project Explanation Video:
https://drive.google.com/drive/folders/10aEoJShgRXxKXVTMobaxA-ItOY42td93?usp=drive_link

⚠️ Important

The Gemini API key previously used in this project has been deleted

must use own Gemini API key

The key must support Gemini 2.5+ models

Docker handles all backend dependencies

🖥️ Frontend Setup
cd frontend
npm install
npm run dev

⚙️ Backend Setup (Docker)

Create environment file:

cp .env.example .env


Add your own Gemini API key in .env:

GEMINI_API_KEY=your_gemini_api_key_here


Build and start backend:

docker-compose up --build



END...
