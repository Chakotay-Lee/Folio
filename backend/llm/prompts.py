import re


def build_genre_suggest_prompt(title: str, summary: str, existing_genres: list[str],
                                language: str = "en") -> str:
    """Prompt to suggest the best genre from existing list, or a new one if none fits."""
    genres_block = "\n".join(f"  - {g}" for g in existing_genres[:80]) if existing_genres else "  (empty)"

    if language == "zh-TW":
        return f"""你是圖書館員 AI。請為以下書籍選出最合適的繁體中文分類。

書名：{title}
摘要：{summary[:500] if summary else '（無）'}

【現有分類清單】
{genres_block}

【規則】
1. 若現有分類中有精確符合本書主題的，直接選用（is_new: false，description 留空）
2. 若現有分類均不適合，提出新的繁體中文分類路徑（is_new: true），並用一句話說明此分類（description）
3. 禁止為了複用而強套不相關的分類
4. 最多 3 層，以 ' > ' 分隔

只輸出合法 JSON，不要有說明：
{{"genre_path": "分類路徑", "is_new": true或false, "description": "新分類說明（is_new=false時留空字串）"}}"""

    if language == "zh-CN":
        return f"""你是图书馆员 AI。请为以下书籍选出最合适的简体中文分类。

书名：{title}
摘要：{summary[:500] if summary else '（无）'}

【现有分类清单】
{genres_block}

【规则】
1. 若现有分类中有精确符合本书主题的，直接选用（is_new: false，description 留空）
2. 若现有分类均不适合，提出新的简体中文分类路径（is_new: true），并用一句话说明此分类（description）
3. 禁止强套不相关的分类
4. 最多 3 层，以 ' > ' 分隔

只输出合法 JSON：
{{"genre_path": "分类路径", "is_new": true或false, "description": "新分类说明（is_new=false时留空字符串）"}}"""

    if language == "ja":
        return f"""あなたは図書館司書 AI です。この書籍に最も適したジャンルを選んでください。

書名：{title}
概要：{summary[:500] if summary else '（なし）'}

【既存ジャンル一覧】
{genres_block}

【ルール】
1. 既存ジャンルに正確に合致するものがあれば選ぶ（is_new: false、description は空文字）
2. 合致するものがなければ新しいジャンルを提案する（is_new: true）、そのジャンルを一文で説明する（description）
3. 無関係なジャンルを無理に当てはめない
4. 最大 3 階層、' > ' 区切り

JSON のみ出力：
{{"genre_path": "ジャンルパス", "is_new": true or false, "description": "新ジャンルの説明（is_new=false のとき空文字）"}}"""

    # English (default)
    return f"""You are a librarian AI. Choose the best genre for this book.

Title: {title}
Summary: {summary[:500] if summary else '(none)'}

[Existing genres]
{genres_block}

[Rules]
1. If an existing genre accurately matches this book, use it (is_new: false, description = "")
2. If none fits, propose a new genre path (is_new: true) and provide a one-sentence description of the genre
3. Never force-fit an unrelated existing genre
4. Max 3 levels separated by ' > '

Output only valid JSON:
{{"genre_path": "genre path here", "is_new": true or false, "description": "one-sentence genre description (empty string when is_new=false)"}}"""


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
4. **準確性優先於複用**：若現有分類清單中有精確符合本書主題的分類，才重用；若無，**必須**自行建立正確的繁體中文分類
5. **嚴禁為了複用而強套不相關的現有分類**；一本物理書不可歸類為程式語言，一本食譜不可歸類為醫學
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
4. **准确性优先于复用**：若现有分类清单中有精确符合本书主题的分类，才复用；若无，**必须**自行建立正确的简体中文分类
5. **严禁为了复用而强套不相关的现有分类**；一本物理书不可归类为编程语言
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
4. **正確性を複用より優先する**：既存リストに本書の主題に正確に合致するものがある場合のみ再利用する。なければ**必ず**正確な日本語ジャンルを新規作成する
5. **無関係な既存分類を無理に適用することを厳禁**とする
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
4. Accuracy over reuse: only reuse an existing genre if it accurately matches this book's subject. If no existing genre fits, you MUST create a correct new one
5. Never force-fit an unrelated existing genre — a physics book must not be filed under programming
{genre_section}
Book text excerpt:
\"\"\"
{content_block}
\"\"\"
"""


def build_genre_names_prompt(parent_genre: str, books: list[dict], language: str = "en") -> str:
    """Phase 1: suggest sub-genre names + descriptions only (no book assignment).

    Input: list of {title, tags}. Output: {"sub_genres": [{"path","description"}]}
    Small output (~300 tokens) so it never truncates.
    """
    titles_block = "\n".join(
        f"  - {b['title']}" + (f" [{', '.join(b['tags'][:4])}]" if b.get('tags') else "")
        for b in books[:200]
    )

    if language == "zh-TW":
        return f"""你是圖書館員 AI。以下是分類「{parent_genre}」下 {len(books)} 本書的書名列表。
請根據這些書名，建議適合的子分類清單（第三層），每個子分類附上一句繁體中文說明。

書名列表：
{titles_block}

規則：
1. 子分類路徑格式：「{parent_genre} > 子分類名稱」
2. 名稱精確、具體（如「Python」而非「程式語言」）
3. 預計 3–10 個子分類即可
4. 新增「{parent_genre} > 其他」作為兜底

只輸出合法 JSON：
{{"sub_genres": [{{"path": "完整路徑", "description": "說明"}}]}}"""

    if language == "zh-CN":
        return f"""你是图书馆员 AI。以下是分类「{parent_genre}」下 {len(books)} 本书的书名列表。
请根据这些书名，建议适合的子分类清单（第三层），每个子分类附上一句简体中文说明。

书名列表：
{titles_block}

规则：
1. 子分类路径格式：「{parent_genre} > 子分类名称」
2. 名称精确、具体（如「Python」而非「编程语言」）
3. 预计 3–10 个子分类即可
4. 新增「{parent_genre} > 其他」作为兜底

只输出合法 JSON：
{{"sub_genres": [{{"path": "完整路径", "description": "说明"}}]}}"""

    if language == "ja":
        return f"""あなたは図書館司書 AI です。ジャンル「{parent_genre}」の {len(books)} 冊の書名リストを見て、適切なサブジャンル（第3階層）を提案してください。各サブジャンルに一文の日本語説明を付けてください。

書名リスト：
{titles_block}

ルール：
1. パス形式：「{parent_genre} > サブジャンル名」
2. 具体的な名前（例：「Python」）
3. 3〜10 個程度
4. 「{parent_genre} > その他」を必ず含める

JSON のみ出力：
{{"sub_genres": [{{"path": "完全なパス", "description": "説明"}}]}}"""

    return f"""You are a librarian AI. Below are {len(books)} book titles under the genre "{parent_genre}".
Suggest appropriate sub-genres (3rd level) with a one-sentence description each.

Book titles:
{titles_block}

Rules:
1. Path format: "{parent_genre} > Sub-genre Name"
2. Use specific names (e.g. "Python", not "Programming Language")
3. Aim for 3–10 sub-genres
4. Always include "{parent_genre} > Other" as a catch-all

Output only valid JSON:
{{"sub_genres": [{{"path": "full path", "description": "description"}}]}}"""


def build_genre_assign_prompt(parent_genre: str, sub_genres: list[dict],
                               books: list[dict], language: str = "en") -> str:
    """Phase 2: assign a batch of books to the proposed sub-genres.

    sub_genres: [{"path": "..."}]
    books: [{"id": "...", "title": "...", "tags": [...]}]
    Output: {"assignments": [{"id": "book_id", "path": "sub_genre_path"}]}
    """
    paths_block = "\n".join(f"  - {sg['path']}" for sg in sub_genres)
    books_block = "\n".join(
        f"  {b['id']}: {b['title']}" + (f" [{', '.join(b['tags'][:4])}]" if b.get('tags') else "")
        for b in books
    )
    other = next((sg['path'] for sg in sub_genres if sg['path'].endswith('> 其他') or sg['path'].endswith('> Other') or sg['path'].endswith('> その他')), sub_genres[-1]['path'] if sub_genres else "")

    if language == "zh-TW":
        return f"""你是圖書館員 AI。請將以下書籍分配到對應的子分類中。

【可用子分類】
{paths_block}

【書籍清單】（格式：id: 書名  [標籤]）
{books_block}

規則：
1. 每本書分配到最合適的子分類
2. 若無合適分類，指定為「{other}」
3. 只輸出合法 JSON：
{{"assignments": [{{"id": "書籍id", "path": "子分類路徑"}}]}}"""

    if language == "zh-CN":
        return f"""你是图书馆员 AI。请将以下书籍分配到对应的子分类中。

【可用子分类】
{paths_block}

【书籍清单】（格式：id: 书名  [标签]）
{books_block}

规则：
1. 每本书分配到最合适的子分类
2. 若无合适分类，指定为「{other}」
3. 只输出合法 JSON：
{{"assignments": [{{"id": "书籍id", "path": "子分类路径"}}]}}"""

    if language == "ja":
        return f"""あなたは図書館司書 AI です。以下の書籍を適切なサブジャンルに割り当ててください。

【サブジャンル一覧】
{paths_block}

【書籍リスト】（形式：id: 書名  [タグ]）
{books_block}

ルール：
1. 各書籍を最も適したサブジャンルに割り当てる
2. 適切なものがなければ「{other}」を使う
3. JSON のみ出力：
{{"assignments": [{{"id": "book_id", "path": "サブジャンルパス"}}]}}"""

    return f"""You are a librarian AI. Assign each book below to the most appropriate sub-genre.

[Available sub-genres]
{paths_block}

[Books] (format: id: title  [tags])
{books_block}

Rules:
1. Pick the best-matching sub-genre for each book
2. Use "{other}" if no good match exists
3. Output only valid JSON:
{{"assignments": [{{"id": "book_id", "path": "sub_genre_path"}}]}}"""
