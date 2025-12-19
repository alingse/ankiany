import unittest
import sys
import os

# 将项目根目录添加到 python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tools import search_web_for_topic


class TestSearchWebTool(unittest.IsolatedAsyncioTestCase):
    async def test_search_web_for_topic_real_request(self):
        """
        Integration test: Performs a real web search using duckduckgo-search.
        """
        query = "Python programming"
        print(f"\nRunning real search test for query: '{query}'...")

        # New format: dict args, call via .handler since it's an SdkMcpTool
        result_dict = await search_web_for_topic.handler({"query": query})

        result_text = result_dict["content"][0]["text"]
        print(f"Search Results (first 200 chars):\n{result_text[:200]}...")

        self.assertIn("content", result_dict)
        self.assertIsInstance(result_text, str)
        self.assertNotEqual(result_text, "No results found.")
        self.assertIn("Title:", result_text)
        self.assertIn("Link:", result_text)
        self.assertGreater(len(result_text), 50)


if __name__ == "__main__":
    unittest.main()
