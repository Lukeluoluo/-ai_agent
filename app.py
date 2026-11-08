# app.py
import json
import asyncio
from datetime import datetime
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain_classic.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tools import LOCAL_TOOLS
from prompt import SYSTEM_PROMPT
from memory import agent_memory
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# 初始化大模型
llm = ChatOpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
    model="deepseek-chat",
    temperature=0
)

class ChatRequest(BaseModel):
    message: str

@app.post("/api/reset")
async def reset_memory():
    """前端刷新时调用的重置接口"""
    agent_memory.reset()
    return {"status": "success"}

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    user_input = req.message
    
    # 1. 组装时间和状态字典
    current_time = datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")
    state_text = agent_memory.get_state_text()
    short_chat_history = agent_memory.get_short_history()

    # 2. 构建 Prompt
    formatted_system = SYSTEM_PROMPT.replace("{long_term_recall}", state_text).replace("{current_time}", current_time)
    # 转义大括号防冲突
    formatted_system = formatted_system.replace("{", "{{").replace("}", "}}")
    
    runtime_prompt = ChatPromptTemplate.from_messages([
        ("system", formatted_system),
        MessagesPlaceholder(variable_name="chat_history"),
        ("user", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    agent = create_openai_tools_agent(llm, LOCAL_TOOLS, runtime_prompt)
    agent_executor = AgentExecutor(agent=agent, tools=LOCAL_TOOLS, verbose=True, max_iterations=50)

    # 3. 定义流式生成器（SSE）
    async def event_generator():
        full_output = ""
        try:
            async for event in agent_executor.astream_events(
                {"input": user_input, "chat_history": short_chat_history}, version="v1"
            ):
                kind = event["event"]
                
                # 捕获大模型的输出文字
                if kind == "on_chat_model_stream":
                    content = event["data"]["chunk"].content
                    if content:
                        full_output += content
                        yield {"data": json.dumps({"type": "message", "content": content}, ensure_ascii=False)}
                
                # 捕获工具调用开始（包含参数）
                elif kind == "on_tool_start":
                    tool_name = event.get("name", "未知工具")
                    tool_input = event.get("data", {}).get("input", {})
                    # 截断过长的参数，防止前端卡顿
                    input_str = json.dumps(tool_input, ensure_ascii=False)
                    if len(input_str) > 100: input_str = input_str[:100] + "..."
                    
                    yield {"data": json.dumps({
                        "type": "tool_start", 
                        "tool": tool_name, 
                        "input": input_str
                    }, ensure_ascii=False)}

                # 捕获工具调用结束（包含返回结果）
                elif kind == "on_tool_end":
                    tool_name = event.get("name", "未知工具")
                    tool_output = event.get("data", {}).get("output", "")
                    # 把结果转成字符串并截断
                    output_str = str(tool_output)
                    if len(output_str) > 150: output_str = output_str[:150] + "..."
                    
                    yield {"data": json.dumps({
                        "type": "tool_end", 
                        "tool": tool_name, 
                        "output": output_str
                    }, ensure_ascii=False)}
                    
            # 结束后更新记忆
            agent_memory.save(user_input, full_output)
            yield {"data": json.dumps({"type": "done"})}

        except Exception as e:
            yield {"data": json.dumps({"type": "error", "content": str(e)})}

    return EventSourceResponse(event_generator())

@app.get("/")
async def get_index():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)