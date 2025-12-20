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


async def run_anki_agent_generator(user_prompt: str, verbose: bool = False):
    """
    Anki Agent 核心逻辑 (Generator).
    """
    # 1. 获取本地工具 Server
    server = get_server()
    server_name = "anki-tools"  # 必须与 tools.py 中的 name 一致

    # 2. 自动生成 allowed_tools 列表
    tools = get_tools_list()
    tool_names = [t.name for t in tools]
    allowed_tools = [f"mcp__{server_name}__{name}" for name in tool_names]

    system_prompt = load_system_prompt()

    yield "--- 启动 Anki Agent ---"
    yield f"已加载工具集 '{server_name}': {tool_names}"
    yield f"正在处理任务: {user_prompt}"
    yield "-" * 30

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
                            yield f"🤖 Claude: {block.text}"
                        elif isinstance(block, ToolUseBlock):
                            # 打印工具调用状态
                            yield f"🛠️  调用工具: {block.name}"
                            if verbose:
                                yield f"    参数: {block.input}"

    except Exception as e:
        yield f"❌ 发生错误: {e}"
        import traceback

        traceback.print_exc()


async def run_anki_agent(user_prompt: str, verbose: bool = False):
    """
    Anki Agent 核心逻辑 (CLI wrapper).
    """
    async for log in run_anki_agent_generator(user_prompt, verbose):
        print(log)
