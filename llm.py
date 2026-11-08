import os
from openai import OpenAI
from dotenv import load_dotenv

# 1. 加载环境变量
load_dotenv()

class LLM:
    def __init__(self):
        # 2. 初始化 DeepSeek 客户端
        self.client = OpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com"
        )
        # 3. 指定使用的模型
        self.model = "deepseek-chat"

    def chat(self, messages: list, tools: list = None):
        """
        与 LLM 进行交互的核心方法
        :param messages: 对话历史列表，格式如 [{"role": "user", "content": "你好"}]
        :param tools: 提供给 LLM 的工具列表（Function Calling 格式）
        :return: LLM 的回复对象
        """
        # 4. 构造请求参数
        kwargs = {
            "model": self.model,
            "messages": messages,
        }
        
        # 5. 如果有工具，就把工具参数加进去
        if tools:
            kwargs["tools"] = tools

        # 6. 发送请求给 DeepSeek
        response = self.client.chat.completions.create(**kwargs)
        
        # 7. 提取并返回核心的 message 对象
        return response.choices[0].message