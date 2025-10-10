# Blog Post Formatting Scripts

This directory contains Python scripts to automatically format and standardize markdown files for the blog, primarily located in the `_posts` directory.

## Recommended Usage

The easiest way to apply all formatting rules is to use the `run_md_tools.sh` script. This script runs the necessary Python scripts in the correct order.

**Prerequisites:**
- Python 3.9 or higher must be installed.

**Execution:**

The script can be run from the root of the repository.

```bash
# Apply formatting to all posts in the default _posts directory
./kkamji_scripts/blog/run_md_tools.sh

# Apply formatting to a different directory
./kkamji_scripts/blog/run_md_tools.sh --root path/to/your/posts
```

**Important:** Before running, it is highly recommended to back up your `_posts` directory, as the scripts will modify files in place.

```bash
# Example: Create a timestamped backup
cp -a _posts _posts_backup_$(date +%Y%m%d%H%M%S)
```

---

## Individual Scripts

The shell script orchestrates the following Python scripts. You can also run them individually if needed.

### 1. `fix_md_h2_rules.py`

- **Purpose**: Enforces consistent horizontal rules (`---`) above all H2 (`##`) headers to improve readability and structure.
- **Features**:
    - Intelligently skips code blocks (```) and YAML front matter.
    - Prevents duplicate horizontal rules.
    - Normalizes spacing around the horizontal rule, ensuring exactly one blank line between the rule and the header.
- **Usage**:
    ```bash
    # Run on the default _posts directory
    python3 kkamji_scripts/blog/fix_md_h2_rules.py

    # Run on a specific file with a dry-run preview
    python3 kkamji_scripts/blog/fix_md_h2_rules.py --file _posts/path/to/post.md --dry-run
    ```

### 2. `renumber_headers.py`

- **Purpose**: Automatically adds and corrects numerical prefixes to headers (e.g., `1.`, `1.1.`, `1.2.1.`).
- **Features**:
    - Starts numbering from H2 (`##`) by default, but is configurable.
    - Skips code blocks.
    - Strips old numbers before applying new ones to ensure correctness.
    - Excludes specific sections like "관련 글" from being numbered.
- **Usage**:
    ```bash
    # Run on the default _posts directory
    python3 kkamji_scripts/blog/renumber_headers.py

    # Start numbering from H3 (###) instead
    python3 kkamji_scripts/blog/renumber_headers.py --min-level 3
    ```