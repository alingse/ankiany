import unittest
import asyncio
import sys
import os

# 将项目根目录添加到 python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tools import read_web_page_content

class TestReadWebTool(unittest.IsolatedAsyncioTestCase):
    async def test_read_web_page_content_real(self):
        """
        Integration test: Reads a real web page and checks content quality.
        """
        # 测试 URL: Python 关于页面 (结构相对清晰)
        url = "https://www.python.org/about/"
        print(f"\nRunning read content test for url: '{url}'...")
        
        # Call via .handler since it's an SdkMcpTool
        result_dict = await read_web_page_content.handler({"url": url})
        
        result_text = result_dict["content"][0]["text"]
        
        print(f"--- Extracted Content Start ---\n{result_text[:500]}\n--- Extracted Content End ---")
        
        self.assertIn("content", result_dict)
        self.assertIsInstance(result_text, str)
        self.assertNotIn("Error reading web page", result_text)
        
        # 验证核心内容是否存在
        self.assertIn("Python", result_text)
        
        # 验证干扰项是否被移除 (Python官网通常有 'Socialize' 这样的页脚标题或导航项)
        # 注意：这取决于具体的页面结构，如果 failing 了说明可能提取太干净或者太脏
        # 我们这里主要验证长度和非空
        self.assertGreater(len(result_text), 200, "Should have substantial content")
        
        # 验证 script 标签内容没有漏出来 (比如 function() {})
        self.assertNotIn("function()", result_text)
        self.assertNotIn("var ", result_text)

if __name__ == '__main__':
    unittest.main()
