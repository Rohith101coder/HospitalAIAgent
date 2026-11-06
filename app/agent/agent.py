import json
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from langchain_openai import ChatOpenAI
from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
    AIMessage,
    ToolMessage,
    BaseMessage
)
from app.core.config import settings
from app.agent.prompts import get_system_prompt
from app.agent.tool_executor import ToolExecutor
from app.agent.tools import get_tools
from app.utils.emergency_check import detect_emergency


class HospitalAgent:
    """Multilingual Hospital Front-Desk Agent using LangChain and OpenRouter."""

    def __init__(self, db: Session):
        self.db = db
        self.executor = ToolExecutor(db=db)
        self.tools = get_tools(self.executor)
        self.tools_map = {t.name: t for t in self.tools}

        # Initialize ChatOpenAI pointing to OpenRouter
        self.llm = ChatOpenAI(
            model=settings.OPENROUTER_MODEL,
            api_key=settings.OPENROUTER_API_KEY,
            base_url=settings.OPENROUTER_BASE_URL,
            temperature=0.2,
            max_tokens=800,
            timeout=settings.OPENROUTER_TIMEOUT_SECONDS,
            max_retries=1
        )
        self.llm_with_tools = self.llm.bind_tools(self.tools)

    def process_message(
        self,
        message: str = "",
        history: Optional[List[Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Process incoming patient message through emergency check and LangChain agent loop.
        Conversation history is received statelessly from the client request.
        """
        text = message or kwargs.get("user_text", "")
        clean_text = text.strip()

        # Step 1: Emergency Check before any LLM or tool execution
        is_emergency, detected_lang, emergency_msg = detect_emergency(clean_text)
        if is_emergency:
            return {
                "reply": emergency_msg,
                "language": detected_lang,
                "is_emergency": True
            }

        # Step 2: Assemble prompt and client-provided history messages
        messages: List[BaseMessage] = [SystemMessage(content=get_system_prompt())]

        if history:
            for item in history:
                # Handle both dicts and Pydantic models (like ChatMessageHistoryItem)
                role = item.get("role") if isinstance(item, dict) else getattr(item, "role", "")
                content = item.get("content") if isinstance(item, dict) else getattr(item, "content", "")
                if role == "user":
                    messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    messages.append(AIMessage(content=content))

        messages.append(HumanMessage(content=clean_text))

        final_reply = ""
        tool_call_count = 0
        max_tool_calls = settings.MAX_TOOL_CALLS

        try:
            while tool_call_count < max_tool_calls:
                response = self.llm_with_tools.invoke(messages)
                messages.append(response)

                # Check if the LLM requested tool executions
                if not response.tool_calls:
                    final_reply = response.content
                    break

                # Execute requested tools
                for tool_call in response.tool_calls:
                    tool_call_count += 1
                    tool_name = tool_call["name"]
                    tool_args = tool_call["args"]
                    call_id = tool_call["id"]

                    if tool_name in self.tools_map:
                        tool_fn = self.tools_map[tool_name]
                        try:
                            tool_result_str = tool_fn.invoke(tool_args)
                        except Exception as e:
                            tool_result_str = json.dumps({"success": False, "error": str(e)})
                    else:
                        tool_result_str = json.dumps({"success": False, "error": f"Unknown tool '{tool_name}'"})

                    messages.append(ToolMessage(content=tool_result_str, tool_call_id=call_id))

                    if tool_call_count >= max_tool_calls:
                        break

            # If finished loop and final_reply not yet set, do one final invoke
            if not final_reply:
                final_ai = self.llm.invoke(messages)
                final_reply = final_ai.content

        except Exception as e:
            error_str = str(e)
            print(f"OpenRouter / Agent invocation error: {error_str}")
            final_reply = (
                "I apologize, our hospital assistant is currently experiencing high server traffic. "
                "Please try sending your message again in a moment, or contact our hospital front desk directly "
                f"at {settings.FRONT_DESK_EMAIL} or emergency {settings.EMERGENCY_NUMBER}."
            )

        return {
            "reply": final_reply,
            "language": "auto",
            "is_emergency": False
        }
