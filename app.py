import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel


TERMINAL_RUN_STATUSES = {"completed", "failed", "cancelled", "expired"}

app = FastAPI(title="CRM Foundry Fabric")

allowed_origins = [
    origin.strip()
    for origin in os.getenv("CRM_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
if allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

static_directory = Path(__file__).parent / "static"
if static_directory.exists():
    app.mount("/static", StaticFiles(directory=static_directory), name="static")


class ChatRequest(BaseModel):
    message: str
    thread_id: Optional[str] = None
    webpage_context: Optional[Dict[str, Any]] = None


def get_project_client() -> AIProjectClient:
    project_endpoint = os.getenv("AZURE_AI_PROJECT_ENDPOINT")
    if not project_endpoint:
        raise HTTPException(
            status_code=500,
            detail="AZURE_AI_PROJECT_ENDPOINT is not configured.",
        )

    return AIProjectClient(
        endpoint=project_endpoint,
        credential=DefaultAzureCredential(),
    )


def format_webpage_context(webpage_context: Dict[str, Any]) -> str:
    context_lines = []
    for key, value in webpage_context.items():
        if isinstance(value, (dict, list)):
            serialized_value = json.dumps(value, ensure_ascii=False)
        else:
            serialized_value = str(value)
        context_lines.append(f"- {key}: {serialized_value}")
    return "\n".join(context_lines)


def extract_latest_assistant_text(messages: Any) -> str:
    for message in getattr(messages, "data", []):
        if getattr(message, "role", None) != "assistant":
            continue

        for content_item in getattr(message, "content", []):
            text_value = getattr(getattr(content_item, "text", None), "value", None)
            if text_value:
                return text_value

    raise HTTPException(
        status_code=500,
        detail="No assistant response was returned from the Foundry agent.",
    )


@app.get("/health")
async def healthcheck() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/api/chat")
async def chat_with_agent(payload: ChatRequest) -> Dict[str, str]:
    agent_id = os.getenv("AZURE_AI_AGENT_ID")
    if not agent_id:
        raise HTTPException(
            status_code=500,
            detail="AZURE_AI_AGENT_ID is not configured.",
        )

    try:
        project_client = get_project_client()
        thread_id = payload.thread_id

        if not thread_id:
            thread = project_client.agents.create_thread()
            thread_id = thread.id

        if payload.webpage_context:
            context_prompt = (
                "[SYSTEM CONTEXT: The user is currently viewing this CRM webpage record:\n"
                f"{format_webpage_context(payload.webpage_context)}\n"
                "Use this context and cross-reference your connected Fabric Lakehouse tools to answer.]"
            )
            project_client.agents.create_message(
                thread_id=thread_id,
                role="user",
                content=context_prompt,
            )

        project_client.agents.create_message(
            thread_id=thread_id,
            role="user",
            content=payload.message,
        )

        run = project_client.agents.create_run(
            thread_id=thread_id,
            assistant_id=agent_id,
        )

        while run.status not in TERMINAL_RUN_STATUSES:
            await asyncio.sleep(1)
            run = project_client.agents.get_run(thread_id=thread_id, run_id=run.id)

        if run.status != "completed":
            raise HTTPException(
                status_code=500,
                detail=f"Agent run did not complete successfully: {run.status}.",
            )

        messages = project_client.agents.list_messages(thread_id=thread_id)
        return {
            "response": extract_latest_assistant_text(messages),
            "thread_id": thread_id,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
