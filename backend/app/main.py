from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import routes

app = FastAPI(
    title="CRM Digital FTE",
    description="Autonomous CRM Digital FTE Factory API",
    version="1.0.0"
)

# Enable CORS for the frontend origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes.router, prefix="/api")

@app.get("/")
async def root():
    return {"message": "CRM Digital FTE API is running."}
