"""Small helper to update the state docs: append a FIXES_SUMMARY row, flip LOOP_STATE status.

usage: python state_update.py TASK "fixes row markdown (without leading |)" NEXT_TASK "plan3lines" "evidence"
"""
import sys
from pathlib import Path

task, row, next_task, plan, evidence = sys.argv[1:6]
p = Path("docs/FIXES_SUMMARY.md")
s = p.read_text(encoding="utf-8")
anchor = "\n## 3. Corrections to context.md"
table_end = s.index(anchor)
# insert row before the blank line preceding section 3
body = s[:table_end].rstrip("\n") + "\n| " + row + " |\n"
s = body + s[table_end:]
p.write_text(s, encoding="utf-8")

p = Path("docs/LOOP_STATE.md")
s = p.read_text(encoding="utf-8")
import re
s = re.sub(rf"\| {re.escape(task)} \| (\w) \| [A-Z_]+ \|", rf"| {task} | \1 | DONE |", s)
s = re.sub(r"- Current task: \S+", f"- Current task: {next_task}", s)
s = re.sub(r"- Last evidence path: .*", f"- Last evidence path: {evidence}", s)
it = int(re.search(r"- Iteration: (\d+)", s).group(1)) + 1
s = re.sub(r"- Iteration: \d+", f"- Iteration: {it}", s)
start = s.index("## Current plan (three lines)")
end = s.index("## Next action")
s = s[:start] + "## Current plan (three lines)\n" + plan.replace("\\n", "\n") + "\n\n" + s[end:]
nstart = s.index("## Next action")
nend = s.index("## Status table")
s = s[:nstart] + f"## Next action\nStart {next_task}.\n\n" + s[nend:]
p.write_text(s, encoding="utf-8")
print("state updated")
