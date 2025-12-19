import os
import asyncio
from typing import Dict, Any, Literal
import genanki
from pydantic import BaseModel
from claude_agent_sdk import tool, create_sdk_mcp_server


# --- Pydantic Models for internal use ---
class AnkiCard(BaseModel):
    model_type: Literal["qa", "cloze"]
    content: str


# --- Tool Implementations ---


@tool(
    "search_web_for_topic",
    "Search the web for a given topic using DuckDuckGo. Returns a summary of search results.",
    {"query": str},
)
async def search_web_for_topic(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    根据给定的查询字符串在网络上进行搜索。
    """
    query = args["query"]
    from duckduckgo_search import DDGS

    print(f"Searching web for: {query}")
    try:
        results = []
        with DDGS() as ddgs:
            ddgs_gen = ddgs.text(query, max_results=5)
            for r in ddgs_gen:
                title = r.get("title", "No Title")
                link = r.get("href", "No Link")
                snippet = r.get("body", "No snippet available.")
                results.append(f"Title: {title}\nLink: {link}\nSnippet: {snippet}\n---")

        text_result = "\n".join(results) if results else "No results found."
        return {"content": [{"type": "text", "text": text_result}]}
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error searching web: {str(e)}"}],
            "is_error": True,
        }


@tool(
    "read_web_page_content",
    "Read the main text content from a given URL.",
    {"url": str},
)
async def read_web_page_content(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    读取并返回指定 URL 的主要文本内容。
    """
    url = args["url"]
    import requests
    from bs4 import BeautifulSoup

    print(f"Reading content from: {url}")
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # 1. 移除彻底无关的标签
        for tag in soup(
            ["script", "style", "noscript", "iframe", "svg", "form", "input", "button"]
        ):
            tag.decompose()

        # 2. 移除通常是导航、页脚、侧边栏的结构性标签
        for tag in soup(["nav", "footer", "header", "aside", "meta", "link"]):
            tag.decompose()

        # 3. 尝试定位核心内容区域
        # 优先查找 <article> 或 <main>，如果存在，只提取这部分内容
        content_area = (
            soup.find("article")
            or soup.find("main")
            or soup.find(
                "div",
                class_=lambda c: c
                and ("content" in c or "article" in c or "post" in c),
            )
        )

        # 如果找到了特定区域，就用那个区域；否则用整个 body
        target_soup = content_area if content_area else soup.body or soup

        # 4. 提取文本并清洗
        text = target_soup.get_text(separator="\n")

        # 逐行处理：去除首尾空白，去除空行
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text_content = "\n".join(chunk for chunk in chunks if chunk)

        # 5. 防止内容过长
        if len(text_content) > 15000:
            text_content = text_content[:15000] + "\n... (content truncated)"

        return {"content": [{"type": "text", "text": text_content}]}
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error reading web page: {str(e)}"}],
            "is_error": True,
        }


@tool(
    "create_anki_package_from_cards",
    "Create an Anki .apkg file from a list of flashcards.",
    {
        "topic": str,
        "cards": list,  # Cards should be a list of objects with model_type and content
    },
)
async def create_anki_package_from_cards(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    接收主题和卡片列表，生成一个 .apkg 文件。
    """
    topic = args["topic"]
    cards_data = args["cards"]
    import uuid

    # --- Debug Logic: Save input to a local JSON file ---
    import json

    # Debug file also gets a timestamp/uuid to prevent overwrite during debug
    debug_suffix = str(uuid.uuid4())[:8]
    debug_filename = f"debug_{topic.replace(' ', '_')}_{debug_suffix}_input.json"
    with open(debug_filename, "w", encoding="utf-8") as f:
        json.dump(args, f, ensure_ascii=False, indent=2)
    print(f"DEBUG: Input data saved to {debug_filename}")
    # --------------------------------------------------

    # 鲁棒性处理：如果 LLM 传过来的是 JSON 字符串而不是列表对象，尝试解析它
    if isinstance(cards_data, str):
        try:
            print("Detected cards_data is a string, attempting to parse as JSON...")
            cards_data = json.loads(cards_data)
        except json.JSONDecodeError as e:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Error: 'cards' argument must be a valid JSON list. Parse error: {str(e)}",
                    }
                ],
                "is_error": True,
            }

    print(f"Creating Anki package for topic: {topic} with {len(cards_data)} cards.")

    # 1. 基础问答模型
    model_qa = genanki.Model(
        1607392319,
        "Simple Q&A Model",
        fields=[{"name": "Question"}, {"name": "Answer"}],
        templates=[
            {
                "name": "Card 1",
                "qfmt": "{{Question}}",
                "afmt": '{{FrontSide}}<hr id="answer">{{Answer}}',
            }
        ],
        css=".card { font-family: arial; font-size: 20px; text-align: center; }",
    )

    # 2. 填空题模型
    model_cloze = genanki.Model(
        1607392320,
        "Simple Cloze Model",
        fields=[{"name": "Text"}],
        templates=[
            {
                "name": "Cloze",
                "qfmt": "{{cloze:Text}}",
                "afmt": "{{cloze:Text}}",
            }
        ],
        model_type=genanki.Model.CLOZE,
        css=".card { font-family: arial; font-size: 20px; text-align: center; }",
    )

    # 3. 选择题模型 (新增)
    model_mcq = genanki.Model(
        1607392321,
        "Simple MCQ Model",
        fields=[{"name": "Question"}, {"name": "Options"}, {"name": "Answer"}],
        templates=[
            {
                "name": "MCQ Card",
                "qfmt": '<div style="text-align:center; font-weight:bold;">{{Question}}</div><br><div style="text-align:left; font-size:18px;">{{Options}}</div>',
                "afmt": '{{FrontSide}}<hr id="answer"><div style="text-align:center; color:green; font-weight:bold;">{{Answer}}</div>',
            }
        ],
        css=".card { font-family: arial; font-size: 20px; }",
    )

    deck_id = abs(hash(topic)) % (10**9)
    my_deck = genanki.Deck(deck_id, f"{topic} 学习包")

    for card_dict in cards_data:
        m_type = card_dict.get("model_type")
        content = card_dict.get("content", "")

        if m_type == "qa":
            parts = content.split("||", 1)
            if len(parts) == 2:
                front, back = parts
                my_note = genanki.Note(
                    model=model_qa, fields=[front.strip(), back.strip()]
                )
                my_deck.add_note(my_note)

        elif m_type == "cloze":
            my_note = genanki.Note(model=model_cloze, fields=[content])
            my_deck.add_note(my_note)

        elif m_type == "mcq":
            # 预期格式: 题目 || 选项(换行分隔) || 答案
            parts = content.split("||")
            if len(parts) >= 3:
                question = parts[0].strip()
                # 选项部分可能包含换行，我们将其转换为 HTML 的换行以便显示
                options = parts[1].strip().replace("\n", "<br>")
                answer = parts[2].strip()
                my_note = genanki.Note(
                    model=model_mcq, fields=[question, options, answer]
                )
                my_deck.add_note(my_note)
            else:
                print(f"Skipping invalid MCQ card: {content[:50]}...")

    # Generate unique filename
    unique_suffix = str(uuid.uuid4())[:8]
    filename = f"{topic.replace(' ', '_').replace('/', '_')}_{unique_suffix}.apkg"
    output_filepath = os.path.join(os.getcwd(), filename)

    genanki.Package(my_deck).write_to_file(output_filepath)

    result_message = f"成功为主题 '{topic}' 创建了 Anki 包。\n- 卡片数量: {len(my_deck.notes)}\n- 文件名: {filename} (已保存，防止覆盖)"
    return {"content": [{"type": "text", "text": result_message}]}


def get_tools_list():
    """
    返回所有工具函数的列表。
    """
    return [search_web_for_topic, read_web_page_content, create_anki_package_from_cards]


def get_server():
    """
    创建并返回 SDK MCP Server 实例。
    """
    return create_sdk_mcp_server(
        name="anki-tools", version="0.1.0", tools=get_tools_list()
    )


if __name__ == "__main__":
    # 简单的本地测试逻辑
    async def test():
        res = await search_web_for_topic({"query": "Python asyncio"})
        print(res)

    asyncio.run(test())
