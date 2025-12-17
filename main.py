
import asyncio
import argparse
from claude_agent.agent import ClaudeAgent
from tools import all_tools

async def main():
    """
    主函数，用于初始化和运行 Claude Agent。
    """
    parser = argparse.ArgumentParser(description="Anki Generator Agent powered by Claude.")
    parser.add_argument("prompt", type=str, help="您希望 Agent 执行的任务，例如 '为我创建一个关于“量子计算”的 Anki 卡片包'")
    args = parser.parse_args()

    print("--- 欢迎使用 Anki 生成 Agent ---")
    print(f"已加载 {len(all_tools)} 个工具: {[tool.name for tool in all_tools]}")
    print("\n注意：Agent 的运行需要有效的 ANTHROPIC_API_KEY 环境变量。")
    print("Agent 将开始思考并执行您的请求，这可能需要几分钟时间，请稍候...")
    print("-" * 20)

    # 1. 初始化 ClaudeAgent 并加载工具
    agent = ClaudeAgent(tools=all_tools)

    # 2. 获取用户输入并启动 Agent
    # get_response 会处理与 Claude 的所有交互，包括多步的工具调用
    try:
        final_response = await agent.get_response(args.prompt)
    except Exception as e:
        print(f"\n--- Agent 执行过程中发生错误 ---")
        print(f"错误类型: {type(e).__name__}")
        print(f"错误信息: {e}")
        print("\n请检查您的网络连接、API 密钥是否有效，或者尝试调整您的提示。")
        return

    # 3. 打印最终结果
    print("\n--- Agent 执行完毕 ---")
    print("Claude 的最终回复:")
    print(final_response)
    print("-" * 20)
    print("\n如果 Agent 成功调用了打包工具，您现在应该可以在项目目录下找到 .apkg 文件。")


if __name__ == "__main__":
    # 使用 asyncio.run 来执行异步的 main 函数
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n--- 用户中断，程序退出 ---")
    except Exception as e:
        print(f"程序启动时发生未知错误: {e}")

