@echo off
echo Starting setup for CRM Digital FTE...

echo 1. Creating Next.js frontend...
call npx -y create-next-app@latest frontend --typescript --tailwind --eslint --app --src-dir --import-alias "@/*" --use-npm

echo 2. Setting up Python backend...
mkdir backend
cd backend
python -m venv venv
call venv\Scripts\activate.bat
pip install fastapi uvicorn sqlalchemy alembic asyncpg pydantic python-jose confluent-kafka google-genai python-dotenv greenlet pgvector
echo Backend setup complete!
cd ..

echo 3. Generating frontend dependencies for Wagmi/RainbowKit...
cd frontend
call npm install wagmi viem @rainbow-me/rainbowkit @tanstack/react-query
cd ..

echo Setup complete!
pause
