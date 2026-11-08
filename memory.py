# memory.py
import json
import os
import re
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.chat_history import InMemoryChatMessageHistory

load_dotenv()

class TripAgentMemory:
    def __init__(self):
        self.history = InMemoryChatMessageHistory()
        
        # 初始化用于管理状态字典的专用大模型
        self.state_llm = ChatOpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com",
            model="deepseek-chat",
            temperature=0
        )
        
        # 初始状态字典
        self.state = {
            "核心锚点": {},
            "强依赖项": {},
            "弱依赖项": {}
        }

    def reset(self):
        """清空所有记忆（历史和状态字典）"""
        self.history = InMemoryChatMessageHistory()
        self.state = {
            "核心锚点": {},
            "强依赖项": {},
            "弱依赖项": {}
        }
        print("🧹 记忆已清空重置")

    def save(self, user_input: str, agent_output: str):
        """保存对话并触发状态字典更新"""
        self.history.add_user_message(user_input)
        self.history.add_ai_message(agent_output)
        self.update_state(user_input, agent_output)

    def get_short_history(self):
        """获取最近 3 轮对话（6条消息）"""
        return self.history.messages[-6:]

    def get_state_text(self) -> str:
        """把字典转成漂亮的文本，方便注入到 System Prompt"""
        if not any(self.state.values()):
            return "【暂无用户画像】"
        
        text = "=====【用户当前旅游状态画像】=====\n"
        for category, items in self.state.items():
            if items:
                text += f"[{category}]\n"
                for k, v in items.items():
                    text += f"  - {k}: {v}\n"
        text += "=================================="
        return text

    def update_state(self, user_input: str, agent_output: str):
        """核心逻辑：让大模型对比旧状态和新对话，执行合并、更新或联动删除"""
        current_state_json = json.dumps(self.state, ensure_ascii=False, indent=2)

        prompt = f"""你是一个高级旅游Agent的记忆状态管理器。
请根据用户的【最新对话】，更新现有的【旅游状态字典】。

【现有状态字典】：
{current_state_json}

【最新对话】：
用户：{user_input}
AI：{agent_output[:500]}... (截断防止太长)

【更新规则】：
1. 提取新对话中的要素，放入对应分类（核心锚点：目的地/天数等；强依赖项：天气/景点等；弱依赖项：口味/预算等）。
2. 如果新信息补充了细节，请合并重写。
3. 如果核心锚点发生冲突变化（如目的地变更为“大理”）：
   - 更新核心锚点。
   - 清空“强依赖项”中与旧目的地相关的数据。
   - 保留“弱依赖项”（如带宠物、不吃辣）。
4. 请严格输出合法的 JSON 格式，不要包含任何 markdown 标记，不要任何解释。

请直接输出更新后的 JSON 字典："""

        try:
            response = self.state_llm.invoke(prompt)
            clean_json = re.sub(r'```json|```', '', response.content).strip()
            self.state = json.loads(clean_json)
        except Exception as e:
            print(f"[系统警告] 状态字典更新失败: {e}")

# 全局导出实例
agent_memory = TripAgentMemory()