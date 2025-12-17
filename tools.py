
import os
from typing import List, Dict, Literal
import genanki
from claude_agent.tools import Tool, get_tools
from pydantic import BaseModel, Field


# --- Pydantic Models for Tool Input ---
# 使用 Pydantic 模型可以为工具的输入参数提供强大的类型检查和文档。
# Claude Agent SDK 能很好地与 Pydantic 集成。

class AnkiCard(BaseModel):
    """定义一张 Anki 卡片的数据结构。"""
    model_type: Literal['qa', 'cloze'] = Field(..., description="卡片类型，'qa' 为问答题，'cloze' 为挖空题。")
    content: str = Field(..., description="卡片内容。对于 'qa' 类型，请用 '||' 分隔问题和答案；对于 'cloze' 类型，请用 '{{c1::...}}' 标记要挖空的部分。")


# --- Tool Implementations ---

class CreateAnkiPackageTool(Tool):
    """
    一个能将结构化卡片数据打包成 .apkg 文件的工具。
    """
    def __init__(self):
        super().__init__("create_anki_package_from_cards")

    def get_tool_function(self):
        def create_anki_package_from_cards(topic: str, cards: List[AnkiCard]) -> str:
            """
            接收主题和卡片列表，生成一个 .apkg 文件。

            Args:
                topic (str): Anki 牌组的主题，例如 'Python 异步编程'。
                cards (List[AnkiCard]): 一个包含 AnkiCard 对象的列表，每张卡片都定义了类型和内容。

            Returns:
                str: 操作结果的描述，例如成功创建的文件路径或错误信息。
            """
            print(f"Received request to create Anki package for topic: {topic} with {len(cards)} cards.")

            # 定义 Anki 模型 (卡片类型)
            model_qa = genanki.Model(
                1607392319,  # 随机生成的 Model ID
                'Simple Q&A Model',
                fields=[{'name': 'Question'}, {'name': 'Answer'}],
                templates=[{
                    'name': 'Card 1',
                    'qfmt': '{{Question}}',
                    'afmt': '{{FrontSide}}<hr id="answer">{{Answer}}',
                }],
                css='.card { font-family: arial; font-size: 20px; text-align: center; }',
            )

            model_cloze = genanki.Model(
                1607392320,  # 另一个随机生成的 Model ID
                'Simple Cloze Model',
                fields=[{'name': 'Text'}],
                templates=[{
                    'name': 'Cloze',
                    'qfmt': '{{cloze:Text}}',
                    'afmt': '{{cloze:Text}}',
                }],
                model_type=genanki.Model.CLOZE,
                css='.card { font-family: arial; font-size: 20px; text-align: center; }',
            )

            deck_id = abs(hash(topic)) % (10**9)
            my_deck = genanki.Deck(deck_id, f'{topic} 学习包')

            for card in cards:
                if card.model_type == 'qa':
                    parts = card.content.split('||', 1)
                    if len(parts) != 2:
                        print(f"Skipping invalid QA card: {card.content}")
                        continue
                    front, back = parts
                    my_note = genanki.Note(model=model_qa, fields=[front.strip(), back.strip()])
                    my_deck.add_note(my_note)
                elif card.model_type == 'cloze':
                    my_note = genanki.Note(model=model_cloze, fields=[card.content])
                    my_deck.add_note(my_note)

            filename = f"{topic.replace(' ', '_').replace('/', '_')}.apkg"
            output_filepath = os.path.join(os.getcwd(), filename)
            genanki.Package(my_deck).write_to_file(output_filepath)
            
            result_message = f"成功为主题 '{topic}' 创建了 Anki 包，包含 {len(my_deck.notes)} 张卡片。文件已保存至: {output_filepath}"
            print(result_message)
            return result_message

        return create_anki_package_from_cards


# 注意：对于 search_web_for_topic 和 read_web_page_content,
# 我们在这里只定义工具类。实际的执行逻辑将由 Gemini Agent 的内置工具
# (google_web_search, web_fetch) 在 Agent 内部处理，
# Claude Agent SDK 会将这些调用路由到 Gemini Agent 的能力上。
# 我们在这里只需要正确地声明工具的名称和 schema。

class SearchWebTool(Tool):
    """
    一个用于在网络上搜索信息的工具。
    """
    def __init__(self):
        super().__init__("search_web_for_topic")
    
    def get_tool_function(self):
        def search_web_for_topic(query: str) -> str:
            """
            根据给定的查询字符串在网络上进行搜索。

            Args:
                query (str): 用于搜索的关键词或问题。

            Returns:
                str: 搜索结果的摘要。
            """
            # 这个函数的实际逻辑将由 Gemini Agent 的 google_web_search 实现
            # 这里我们只需要一个符合签名的占位符
            pass
        return search_web_for_topic

class ReadWebPageTool(Tool):
    """
    一个用于读取指定 URL 网页内容的工具。
    """
    def __init__(self):
        super().__init__("read_web_page_content")

    def get_tool_function(self):
        def read_web_page_content(url: str) -> str:
            """
            读取并返回指定 URL 的主要文本内容。

            Args:
                url (str): 要读取的网页的完整 URL。

            Returns:
                str: 网页的主要文本内容。
            """
            # 这个函数的实际逻辑将由 Gemini Agent 的 web_fetch 实现
            # 这里我们只需要一个符合签名的占位符
            pass
        return read_web_page_content


# get_tools() 会自动发现当前文件中所有 Tool 的子类并返回它们的实例
all_tools = get_tools()

if __name__ == '__main__':
    # 这个部分可以用于单独测试工具
    print(f"Discovered {len(all_tools)} tools.")
    for tool in all_tools:
        print(f"- Tool: {tool.name}")
        # 简单测试 Anki 打包工具
        if tool.name == "create_anki_package_from_cards":
            test_cards = [
                AnkiCard(model_type='qa', content='Python 是什么？||一种解释型、面向对象、动态数据类型的高级程序设计语言。'),
                AnkiCard(model_type='cloze', content='{{c1::Guido van Rossum}} 在 1989 年圣诞节期间开始编写 Python 语言。')
            ]
            tool.get_tool_function()("Python 基础", test_cards)
