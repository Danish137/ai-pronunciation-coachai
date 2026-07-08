# PronounceAI

PronounceAI is a full-stack pronunciation assessment app for short English recordings. It supports browser recording, file upload, word-level issue highlighting, AI coaching, anonymous session history, and DPDP-aware data handling.

## Stack

- Frontend: React, TypeScript, Vite, TanStack Query, Axios
- Backend: FastAPI, SQLAlchemy, Pydantic Settings
- Audio pipeline: FFmpeg / FFprobe
- Providers: Azure Speech, Groq, database via `DATABASE_URL`

## Local Setup

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

### Backend

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
pip install -r backend\requirements.providers.txt
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

## Environment

Copy `.env.example` to `.env` and fill in values. The backend runs in mock mode by default so the product can work end-to-end before Azure or Groq keys are added.

For the real provider path:

- Set `ENABLE_MOCK_ANALYSIS=false`
- Install `backend/requirements.providers.txt`
- Add Azure Speech and Groq keys to `.env`

## Notes

- FFmpeg and FFprobe should be available on the server `PATH`
- Raw audio is written to temp storage only for processing and deleted afterwards
- History stores assessment metadata, not permanent audio
