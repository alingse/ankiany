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
    import json
    import hashlib
    import html

    # --- Debug Logic: Save input to a local JSON file ---
    debug_suffix = str(uuid.uuid4())[:8]
    debug_filename = f"debug_{topic.replace(' ', '_')}_{debug_suffix}_input.json"
    with open(debug_filename, "w", encoding="utf-8") as f:
        json.dump(args, f, ensure_ascii=False, indent=2)
    print(f"DEBUG: Input data saved to {debug_filename}")
    # --------------------------------------------------

    # 鲁棒性处理：如果 LLM 传过来的是 JSON 字符串而不是列表对象，尝试解析它
    if isinstance(cards_data, str):
        try:
            # Try loading directly first; if it fails, try a more aggressive cleanup.
            try:
                cards_data = json.loads(cards_data)
            except json.JSONDecodeError:
                # Remove non-printable characters except common whitespace
                import re

                cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", cards_data)
                cards_data = json.loads(cleaned)
            print("Successfully parsed cards_data from string.")
        except Exception as e:
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

    # Generate a stable deck ID based on topic
    deck_id = int(hashlib.sha256(topic.encode("utf-8")).hexdigest()[:8], 16)
    my_deck = genanki.Deck(deck_id, f"{topic} 学习包")

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

    # 3. 选择题模型
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

    skipped_count = 0
    added_count = 0

    for card_dict in cards_data:
        m_type = card_dict.get("model_type")
        content = card_dict.get("content", "").strip()
        if not content:
            print("WARNING: Skipped card (Empty content)")
            skipped_count += 1
            continue

        note = None
        if m_type == "qa":
            # Using split("||", 1) is safer to ensure we get exactly two parts if they exist
            # and don't lose the rest of the content if there are more ||
            parts = content.split("||", 1)
            if len(parts) == 2:
                front, back = parts[0], parts[1]
                # HTML escape first, then replace newlines with <br>
                front_html = html.escape(front.strip()).replace("\n", "<br>")
                back_html = html.escape(back.strip()).replace("\n", "<br>")
                note = genanki.Note(
                    model=model_qa,
                    fields=[front_html, back_html],
                    guid=genanki.guid_for(front.strip(), back.strip(), topic),
                )
            else:
                # Try fallback split with \n\n or \n
                parts = content.split("\n\n", 1)
                if len(parts) == 2:
                    front, back = parts
                    front_html = html.escape(front.strip()).replace("\n", "<br>")
                    back_html = html.escape(back.strip()).replace("\n", "<br>")
                    note = genanki.Note(
                        model=model_qa,
                        fields=[front_html, back_html],
                        guid=genanki.guid_for(front.strip(), back.strip(), topic),
                    )
                else:
                    print(
                        f"WARNING: Skipped QA card (Missing '||' separator): {content[:50]}..."
                    )
                    skipped_count += 1

        elif m_type == "cloze":
            # Ensure it contains at least one cloze deletion
            if "{{c" not in content:
                content = f"{{{{c1::{content}}}}}"

            # For cloze, we want to escape the content BUT preserve the {{c1::...}} tags.
            # This is tricky because html.escape will turn {{ into {{ etc (actually { is safe in HTML usually, but < > & " ' are not).
            # genanki expects the {{c1::...}} syntax to remain intact for processing, but the *content* inside and outside should be HTML safe.
            # However, standard practice with genanki is to just pass the string.
            # If we simply html.escape everything, {{c1::foo}} becomes {{c1::foo}} which is fine as { is not escaped by default in python's html.escape unless quote=True? No, { is not escaped.
            # Let's check: html.escape('<foo>') -> '&lt;foo&gt;'.
            # html.escape('{{c1::foo}}') -> '{{c1::foo}}'.
            # So simple html.escape should be safe for the Cloze tags themselves, assuming they don't contain < or > inside the control chars (which they don't).
            # BUT, if the user put <br> or other HTML in their content intentionally (which the prompt might do? No, prompt outputs plain text mostly),
            # we are now escaping it. The prompt says "content: string", usually plain text.
            # The previous code was replacing \n with <br>.

            content_html = html.escape(content.strip()).replace("\n", "<br>")
            note = genanki.Note(
                model=model_cloze,
                fields=[content_html],
                guid=genanki.guid_for(content.strip(), topic),
            )

        elif m_type == "mcq":
            parts = content.split("||")
            if len(parts) >= 3:
                question = html.escape(parts[0].strip()).replace("\n", "<br>")
                options = html.escape(parts[1].strip()).replace("\n", "<br>")
                answer = html.escape(parts[2].strip()).replace("\n", "<br>")
                note = genanki.Note(
                    model=model_mcq,
                    fields=[question, options, answer],
                    guid=genanki.guid_for(question, options, topic),
                )
            else:
                print(
                    f"WARNING: Skipped MCQ card (Missing '||' parts or insufficient parts): {content[:50]}..."
                )
                skipped_count += 1

        if note:
            my_deck.add_note(note)
            added_count += 1

    # Generate unique filename
    unique_suffix = str(uuid.uuid4())[:8]
    filename = f"{topic.replace(' ', '_').replace('/', '_')}_{unique_suffix}.apkg"

    from session_context import output_dir_var

    target_dir = output_dir_var.get() or os.getcwd()
    output_filepath = os.path.join(target_dir, filename)

    genanki.Package(my_deck).write_to_file(output_filepath)

    result_message = (
        f"成功为主题 '{topic}' 创建了 Anki 包。\n"
        f"- 总输入卡片: {len(cards_data)}\n"
        f"- 成功添加: {added_count}\n"
        f"- 跳过(格式错误): {skipped_count}\n"
        f"- 文件名: {filename}"
    )
    print(result_message)
    return {"content": [{"type": "text", "text": result_message}]}


def get_tools_list():
    """
    返回所有工具函数的列表。
    """
    return [
        search_web_for_topic,
        read_web_page_content,
        create_anki_package_from_cards,
    ]


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
