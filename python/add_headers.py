import os
import re


def process_file(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        content = file.read()

    # '## ' 로 시작하는 헤더 이전 줄에 '---' 삽입
    # 패턴 설명:
    #   - r'(\n)(## )': 개행(\n) + "## "으로 시작하는 부분을 찾음
    #   - r'\1---\1\2': 첫 번째 그룹(개행) 후에 '---' + 다시 개행 + 두 번째 그룹(## )을 삽입
    # 결과적으로 {이전 내용}\n---\n## 제목 형태가 됨
    updated_content = re.sub(r"(\n)(## )", r"\1---\1\2", content)

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
