import asyncio
import argparse
import sys
import os

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    AssistantMessage,
    TextBlock,
    ToolUseBlock
)
from tools import get_server, get_tools_list

async def main():
    """
    Anki Agent 主入口。
    使用 Claude SDK Client 驱动本地定义的工具 (MCP Server)。
    """
    parser = argparse.ArgumentParser(description="Anki Generator Agent powered by Claude.")
    parser.add_argument("prompt", type=str, help="您希望 Agent 执行的任务")
    parser.add_argument("--verbose", action="store_true", help="显示详细的工具调用日志")
    args = parser.parse_args()

    # 1. 获取本地工具 Server
    server = get_server()
    server_name = "anki-tools" # 必须与 tools.py 中的 name 一致

    # 2. 自动生成 allowed_tools 列表
    # MCP 工具的完整名称格式通常是: mcp__{server_name}__{tool_name}
    tools = get_tools_list()
    tool_names = [t.name for t in tools]
    allowed_tools = [f"mcp__{server_name}__{name}" for name in tool_names]

    print(f"--- 启动 Anki Agent ---")
    print(f"已加载工具集 '{server_name}': {tool_names}")
    print(f"正在处理任务: {args.prompt}")
    print("-" * 30)

    # 3. 定义 System Prompt
    system_prompt = """
你是一个专业的 Anki 卡片制作专家 Agent。你的目标是帮助用户将任何主题转化为高质量的 Anki 记忆卡片 (.apkg)。

请严格遵循以下工作流程：

1.  **分析与策略判断**：
    *   首先判断用户的主题。
    *   **优先使用已有知识**：如果你对该主题非常熟悉，**请跳过搜索步骤**，直接利用你的内部知识生成。
    *   **仅在必要时搜索**：只有当主题涉及最新时事、极冷门知识时，才使用搜索工具（限制3次，精读3-5个网页）。

2.  **内容规划 (50题标准)**：
    *   **数量要求**：必须生成 **至少 50 道** 题目，以确保覆盖面的广度。
    *   **题型配比**：
        *   30% 基础概念 (QA/选择题)
        *   40% 核心原理与逻辑 (填空题/QA)
        *   30% 实战场景与易错点 (选择题/QA)

3.  **生成与打包 (严格数据格式)**：
    *   调用 `create_anki_package_from_cards` 工具。
    *   **必须严格**遵循以下 JSON 结构构造 `cards` 参数：

    ```json
    {
        "model_type": "qa" | "cloze" | "mcq",
        "content": "string"
    }
    ```

    **详细格式规范：**
    *   **类型 A: 问答题 (`qa`)**
        *   `content`: `问题文本||答案文本`
        *   *示例*: `"MySQL 默认端口是多少？||3306"`

    *   **类型 B: 填空题 (`cloze`) - 核心逻辑挖空**
        *   **要求**：不要挖掘简单的名词，要挖掘**核心逻辑**、**因果关系**或**关键参数**。
        *   `content`: 使用 `{{c1::...}}` 标记。
        *   *示例*: `"InnoDB 使用 {{c1::MVCC}} 来实现高并发下的读写不冲突，而非单纯的行锁。"`

    *   **类型 C: 选择题 (`mcq`) - 新增**
        *   `model_type`: "mcq"
        *   `content`: 必须包含 **两个** `||` 分隔符。
        *   格式：`题目描述||选项A\n选项B\n选项C\n选项D||正确答案`
        *   *示例*: `{"model_type": "mcq", "content": "下列哪个不是 MySQL 的存储引擎？||A. InnoDB\nB. MyISAM\nC. Redis\nD. Memory||C. Redis"}`

    *   **最终动作**：将生成的 50+ 张卡片组装成一个列表，一次性传入工具。

**重要提示**：
*   **不要偷懒**，数量必须达标。
*   文件名会自动生成防止覆盖，你只需要关注内容质量。
"""

    # 4. 配置 Agent 选项
    options = ClaudeAgentOptions(
        mcp_servers={server_name: server},
        allowed_tools=allowed_tools,
        system_prompt=system_prompt
    )

    try:
        # 5. 启动 Client 并发送查询
        async with ClaudeSDKClient(options=options) as client:
            await client.query(args.prompt)

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
                            if args.verbose:
                                print(f"    参数: {block.input}")

    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 用户取消操作。")