# main.py
import os
from datetime import datetime
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_classic.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# 导入自定义模块
from tools import LOCAL_TOOLS
from prompt import SYSTEM_PROMPT
from memory import agent_memory

# 加载环境变量
load_dotenv()

# 初始化主大模型 (DeepSeek)
llm = ChatOpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
    model="deepseek-chat",
    temperature=0
)

if __name__ == "__main__":
    print("===== 🧳 AI旅行规划Agent【时空感知 + 状态字典 + 路线导航版】 =====")
    print("输入你的旅行需求，输入 quit 退出\n")

    while True:
        user_input = input("👤 用户：")
        if user_input.strip().lower() == "quit":
            print("程序退出")
            break

        # 1. 获取当前真实系统时间
        current_time = datetime.now().strftime("%Y年%m月%d日 %H:%M:%S (星期%w)")

        # 2. 获取最近 3 轮对话（短期记忆）
        short_chat_history = agent_memory.get_short_history()
        
        # 3. 获取高度浓缩的全局状态字典（长期记忆）
        state_text = agent_memory.get_state_text()
        
        # 4. 组装 System Prompt
        # 先用 replace 替换状态字典和时间占位符
        formatted_system = SYSTEM_PROMPT.replace("{long_term_recall}", state_text)
        formatted_system = formatted_system.replace("{current_time}", current_time)
        
        # ⚠️【核心修复】转义所有大括号，防止 LangChain 把 {坐标1} 当成变量
        formatted_system = formatted_system.replace("{", "{{").replace("}", "}}")
        
        # 5. 构建动态 Prompt 模板
        runtime_prompt = ChatPromptTemplate.from_messages([
            ("system", formatted_system),
            MessagesPlaceholder(variable_name="chat_history"),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        # 6. 构建 Agent 并运行
        agent = create_openai_tools_agent(llm, LOCAL_TOOLS, runtime_prompt)
        
        agent_executor = AgentExecutor(
            agent=agent,
            tools=LOCAL_TOOLS,
            verbose=True,
            max_iterations=50,
            handle_parsing_errors=True
        )

        # 7. 执行 Agent
        try:
            resp = agent_executor.invoke({
                "input": user_input,
                "chat_history": short_chat_history
            })
            
            output = resp["output"]
            print(f"\n🤖 Agent:\n{output}\n")

            # 8. 保存对话，并在后台触发状态字典更新
            print("[系统后台] 正在更新用户状态字典...")
            agent_memory.save(user_input, output)
            print(f"[当前状态]: {agent_memory.state}\n")
            
        except Exception as e:
            print(f"\n❌ 运行报错了：{str(e)}")
            print("如果是 API 报错，请检查 Key 或网络；如果是工具报错，请往上翻看日志。")