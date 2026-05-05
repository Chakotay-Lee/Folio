import re


def _is_traditional_chinese_genre(g: str) -> bool:
    """Return True only if genre path has no ASCII words AND no Simplified-only characters."""
    if re.search(r'[A-Za-z]', g):
        return False
    simplified_chars = set('运动医饮艺绘经传临国际认识专业专项组织')
    return not any(c in simplified_chars for c in g)


def build_extraction_prompt(text: str, existing_genres: list[str] | None = None,
                             filename_hint: str | None = None, language: str = "en") -> str:
    # Build genre hint block
    if existing_genres and language == "zh-TW":
        clean = sorted({g for g in existing_genres if g and _is_traditional_chinese_genre(g)})[:60]
        if clean:
            genres_block = "\n".join(f"  - {g}" for g in clean)
            genre_section = f"""
【書庫現有分類（請優先從中選擇，保持一致性）】
（以下皆為繁體中文分類，簡體中文分類請忽略）
{genres_block}

"""
        else:
            genre_section = ""
    elif existing_genres and language != "zh-TW":
        clean = sorted({g for g in existing_genres if g})[:60]
        if clean:
            genres_block = "\n".join(f"  - {g}" for g in clean)
            genre_section = f"\nExisting genres (reuse when appropriate):\n{genres_block}\n\n"
        else:
            genre_section = ""
    else:
        genre_section = ""

    # Content block
    if not text.strip() and filename_hint:
        if language == "zh-TW":
            content_block = f'[無法提取文字，請根據書名判斷分類，必須給出 genre_path]\n書名：{filename_hint}'
        elif language == "zh-CN":
            content_block = f'[无法提取文字，请根据书名判断分类，必须给出 genre_path]\n书名：{filename_hint}'
        elif language == "ja":
            content_block = f'[テキスト抽出不可。書名からジャンルを判断し genre_path を必ず指定]\n書名：{filename_hint}'
        else:
            content_block = f'[No text extracted. Use filename to determine genre_path.]\nFilename: {filename_hint}'
    else:
        content_block = text[:4000]

    if language == "zh-TW":
        return f"""你是一位圖書館員 AI。請分析以下書籍文字節選，提取後設資料。

只輸出合法 JSON，不要有任何說明或 markdown：
{{
  "title": "書名（保留原文，不翻譯）",
  "author": "作者（字串或 null）",
  "summary": "繁體中文摘要（500字以內）",
  "tags": ["繁體中文標籤陣列", "最多 12 個"],
  "genre_path": "【必填，不可空白】繁體中文分類路徑"
}}

【分類規則】
1. genre_path **必填**，根據書名或內容判斷，絕對不可留空
2. genre_path **嚴格使用繁體中文**，絕對禁止英文或簡體中文
3. 最多 3 層，以 ' > ' 分隔
4. **優先重用書庫現有繁體中文分類**（見下方清單），避免重複建立同義分類
5. 只有現有分類確實無法描述時，才可新增繁體中文分類
{genre_section}
書籍文字節選：
\"\"\"
{content_block}
\"\"\"
"""

    if language == "zh-CN":
        return f"""你是一位图书馆员 AI。请分析以下书籍文字节选，提取元数据。

只输出合法 JSON，不要有任何说明或 markdown：
{{
  "title": "书名（保留原文，不翻译）",
  "author": "作者（字符串或 null）",
  "summary": "简体中文摘要（500字以内）",
  "tags": ["简体中文标签数组", "最多 12 个"],
  "genre_path": "【必填，不可为空】简体中文分类路径"
}}

【分类规则】
1. genre_path **必填**，根据书名或内容判断，绝对不可为空
2. genre_path **严格使用简体中文**
3. 最多 3 层，以 ' > ' 分隔
4. 优先重用现有分类（见下方清单）
{genre_section}
书籍文字节选：
\"\"\"
{content_block}
\"\"\"
"""

    if language == "ja":
        return f"""あなたは図書館司書 AI です。以下の書籍テキスト抜粋を分析し、メタデータを抽出してください。

説明や markdown なしで、合法的な JSON のみを出力してください：
{{
  "title": "書名（原文のまま、翻訳しない）",
  "author": "著者（文字列または null）",
  "summary": "日本語の要約（500文字以内）",
  "tags": ["日本語タグ配列", "最大12個"],
  "genre_path": "【必須、空白不可】日本語ジャンルパス"
}}

【分類ルール】
1. genre_path は**必須**。書名または内容から判断し、絶対に空白にしない
2. genre_path は**日本語のみ**使用
3. 最大3階層、' > ' で区切る
4. 既存のジャンルを優先的に再利用する（下記リスト参照）
{genre_section}
書籍テキスト抜粋：
\"\"\"
{content_block}
\"\"\"
"""

    # English (default)
    return f"""You are a librarian AI. Analyze the following book text excerpt and extract metadata.

Output only valid JSON with no explanation or markdown:
{{
  "title": "Book title (preserve original, do not translate)",
  "author": "Author name (string or null)",
  "summary": "English summary (under 200 words)",
  "tags": ["English tag array", "up to 12 tags"],
  "genre_path": "[REQUIRED, never empty] English genre path"
}}

[Genre rules]
1. genre_path is REQUIRED — infer from title or content, never leave blank
2. Use English only for genre_path
3. Maximum 3 levels separated by ' > '
4. Reuse existing genres when possible (see list below)
{genre_section}
Book text excerpt:
\"\"\"
{content_block}
\"\"\"
"""
