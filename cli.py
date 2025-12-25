import asyncio
import argparse
import sys
import time
from core import run_anki_agent


async def main():
    parser = argparse.ArgumentParser(description="Anki Generator Agent CLI.")
    parser.add_argument("prompt", type=str, help="您希望 Agent 执行的任务")
    parser.add_argument("--verbose", action="store_true", help="显示详细的工具调用日志")
    args = parser.parse_args()

    start_time = time.perf_counter()
    await run_anki_agent(args.prompt, args.verbose)
    end_time = time.perf_counter()

    print(f"\n⏱️ 总耗时: {end_time - start_time:.2f} 秒")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 用户取消操作。")
        sys.exit(0)
