# Claude AI Agent 开发指南 - Anki 卡片生成器项目

本文档为 Claude AI Agent 在 Anki 卡片生成器项目中工作时的重要知识点和最佳实践。

## 🎯 项目概述

本项目是一个基于 Claude SDK 的 Anki 卡片生成器，能够将任意主题转化为高质量的 Anki 记忆卡片 (.apkg 文件)。

### 核心功能
- 使用 Claude Agent SDK 驱动的智能卡片生成
- 支持多种题型：问答题 (qa)、填空题 (cloze)、选择题 (mcq)
- 自动网络搜索和内容整合
- 批量生成 50+ 题目的完整卡片集

## 🚀 技术栈与工具

### uv 包管理器使用

**关键原则**: 此项目使用 uv 作为包管理器，所有 Python 相关命令都需要通过 `uv run` 执行。

#### ✅ 正确的命令格式
```bash
# 语法检查
uv run python -m py_compile script.py

# 代码格式化
uv run ruff format .

# 代码检查
uv run ruff check .

# 运行 Python 脚本
uv run python script.py

# 安装依赖
uv add package_name

# 运行测试
uv run pytest

# 代码检查和自动修复
uv run ruff check --fix .
```

#### ❌ 错误的命令格式
```bash
# 不要直接使用 python
python script.py
python -m py_compile script.py
python3 script.py

# 不要直接使用 ruff
ruff format .
ruff check .
```

### 项目结构

```
ankiany/
├── main.py              # 主入口文件，Claude Agent 客户端
├── tools.py             # MCP Server 定义，包含所有工具
├── tests/               # 测试文件
│   ├── test_tools.py
│   └── test_read_tool.py
├── pyproject.toml       # 项目配置和依赖
└── AGENTS.md           # 本文档
```

### 核心依赖包
- `claude-agent-sdk`: Claude Agent SDK 核心
- `genanki`: Anki 卡片生成库
- `beautifulsoup4`: 网页内容解析
- `duckduckgo-search`: 网络搜索
- `fastapi`: Web API 框架

## 🔧 代码质量标准

- **格式化**: 使用 `ruff format` 进行代码格式化
- **静态检查**: 使用 `ruff check` 进行代码质量检查
- **语法验证**: 使用 `uv run python -m py_compile` 验证语法正确性
- **错误处理**: 所有异常都必须有适当的日志记录和堆栈跟踪

### 错误处理最佳实践

```python
import logging
import traceback

logger = logging.getLogger(__name__)

# 好的错误处理示例
try:
    # 业务逻辑
    result = some_function()
except Exception as e:
    logger.error(f"操作失败: {e}")
    logger.error(f"详细错误堆栈:\n{traceback.format_exc()}")
    # 处理错误或重新抛出
    raise
```

## 🛠️ 开发工作流程

### 代码探索指南

当需要探索或修改代码时：

1. **使用正确的工具搜索文件**:
   - 查找文件: `Glob` 或 `find` 命令
   - 搜索代码: `Grep` 工具，而非 `rg` 或 `grep`

2. **理解项目架构**:
   - `main.py`: Claude Agent 客户端入口
   - `tools.py`: MCP Server 和工具定义
   - 测试文件: 了解功能的预期行为

3. **修改代码前的准备**:
   - 先读取相关文件，理解现有实现
   - 查看相关测试，了解预期行为
   - 使用 TodoWrite 工具规划修改步骤

### 常用命令备忘录

```bash
# 开发环境设置
uv sync

# 检查代码质量
uv run ruff check .
uv run ruff format .

# 运行应用
uv run python main.py "你的提示词"

# 运行测试
uv run pytest

# 安装新依赖
uv add package_name
```

## 📋 Agent 工作规范

### 代码质量检查流程

**在修改完成代码之后，报告完成之前，必须执行以下代码质量检查流程：**

1. **代码质量检查**: 运行 `uv run ruff check .` 检查代码质量问题
2. **代码格式化**: 运行 `uv run ruff format .` 格式化代码
3. **问题修复**: 如果 ruff check 发现问题，必须修复所有问题
4. **语法验证**: 使用 `uv run python -m py_compile` 验证修改的文件
5. **功能测试**: 在提交前进行基本的功能测试
6. **文档更新**: 更新相关文档和注释

### 文件命名约定

- **脚本文件**: `snake_case.py` (如: `main.py`)
- **模块文件**: `snake_case.py` (如: `tools.py`)
- **配置文件**: `pyproject.toml`, `README.md`
- **文档文件**: `KEBAB-CASE.md` (如: `AGENTS.md`)

### Git 提交规范

```bash
# 提交代码
git add .
git commit -m "feat: 添加新功能"
git commit -m "fix: 修复bug"
git commit -m "docs: 更新文档"

# 推送代码
git push origin main
```

## 🎯 Anki 卡片生成规范

### 题型定义

1. **问答题 (qa)**:
   - 格式: `问题文本||答案文本`
   - 示例: `"MySQL 默认端口是多少？||3306"`

2. **填空题 (cloze)**:
   - 格式: 使用 `{{c1::...}}` 标记
   - 示例: `"InnoDB 使用 {{c1::MVCC}} 来实现高并发"`

3. **选择题 (mcq)**:
   - 格式: `题目描述||选项A\n选项B\n选项C\n选项D||正确答案`
   - 示例: `"下列哪个不是 MySQL 的存储引擎？||A. InnoDB\nB. MyISAM\nC. Redis\nD. Memory||C. Redis"`

### 卡片数据结构

```json
{
    "model_type": "qa" | "cloze" | "mcq",
    "content": "string"
}
```

## 📚 重要提醒

- **永远使用 uv 命令**: 所有 Python 相关操作都必须通过 `uv run` 执行
- **保持代码整洁**: 每次修改后都要运行格式化和检查
- **详细错误日志**: 所有关键操作都要有完整的错误日志和堆栈跟踪
- **测试驱动**: 修改代码前先了解现有测试，确保不破坏现有功能
- **探索代码**: 使用适当的工具（Glob、Grep、Read）而非直接 bash 命令

---

**最后更新**: 2025-12-19
**维护者**: Claude AI Agent