import os
import re


def process_file(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        content = file.read()

    # 정규 표현식으로 `---\n## ` 직전에 빈 줄을 추가
    # 패턴 설명:
    #   (\n---\n): 줄바꿈 + "---" + 줄바꿈
    #   (## ): "## " 문자열
    # 치환 시 1번 그룹 뒤에 \n(빈 줄) 추가 => \1\n\2
    updated_content = re.sub(r"(\n---\n)(## )", r"\1\n\2", content)

    with open(file_path, "w", encoding="utf-8") as file:
        file.write(updated_content)


def process_directory(directory):
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".md"):
                process_file(os.path.join(root, file))


if __name__ == "__main__":
    posts_directory = "_posts"
    process_directory(posts_directory)
