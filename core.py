import os
from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    AssistantMessage,
    TextBlock,
    ToolUseBlock,
)
from tools import get_server, get_tools_list


def load_system_prompt():
    prompt_path = os.path.join(os.path.dirname(__file__), "prompt.txt")
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


async def run_anki_agent(user_prompt: str, verbose: bool = False):
    """
    Anki Agent 核心逻辑。
    """
    # 1. 获取本地工具 Server
    server = get_server()
    server_name = "anki-tools"  # 必须与 tools.py 中的 name 一致

    # 2. 自动生成 allowed_tools 列表
    tools = get_tools_list()
    tool_names = [t.name for t in tools]
    allowed_tools = [f"mcp__{server_name}__{name}" for name in tool_names]

    system_prompt = load_system_prompt()

    print("--- 启动 Anki Agent ---")
    print(f"已加载工具集 '{server_name}': {tool_names}")
    print(f"正在处理任务: {user_prompt}")
    print("-" * 30)

    # 3. 配置 Agent 选项
    options = ClaudeAgentOptions(
        mcp_servers={server_name: server},
        allowed_tools=allowed_tools,
        system_prompt=system_prompt,
    )

    try:
        # 4. 启动 Client 并发送查询
        async with ClaudeSDKClient(options=options) as client:
            await client.query(user_prompt)

            # 5. 实时处理响应流
            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            # 打印 Claude 的思考或回答
                            print(f"\n🤖 Claude: {block.text}")
                        elif isinstance(block, ToolUseBlock):
                            # 打印工具调用状态
                            print(f"\n🛠️  调用工具: {block.name}")
                            if verbose:
                                print(f"    参数: {block.input}")

    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback

        traceback.print_exc()
