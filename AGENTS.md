## Code Exploration (`codegraph`)
- Before using `search_files` or `read_file` to map architecture, trace callers/callees, or check blast radius, call `codegraph_explore` first.
- Fall back to `search_files` only for literal string/regex matches, configuration keys, or non-code assets (YAML, Markdown, SQL migrations).
