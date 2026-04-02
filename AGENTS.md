## Gemini Added Memories
- File deletion operations must be restricted to files within the workspace directory. Verify paths before executing any shell commands that delete files (e.g., rm, del, erase) to ensure they do not target files outside the project root.

# Jira 작업 지침
Jira 관련 요청은 반드시 아래 Python 스크립트를 사용할 것.

# Jira — 이슈 읽기
python "C:\\Users\\unkno\\tools\\jira-rest\\scripts\\parse_issue.py" [이슈키] --mode full
# Jira — 이슈 생성
python "C:\\Users\\unkno\\tools\\jira-rest\\scripts\\jira_write.py" create --project [PROJECT] --type [TYPE] --title "[제목]"
python "C:\\Users\\unkno\\tools\\jira-rest\\scripts\\jira_write.py" create --project [PROJECT] --type Bug --title "[제목]" --desc "[설명]" --priority High
# Jira — 이슈 수정
python "C:\\Users\\unkno\\tools\\jira-rest\\scripts\\jira_write.py" update [이슈키] --status "[상태]" --labels "Codex"
# Jira — 댓글 작성
python "C:\\Users\\unkno\\tools\\jira-rest\\scripts\\jira_write.py" comment [이슈키] "[댓글내용]"
# Confluence — 검색
python "C:\\Users\\unkno\\tools\\jira-rest\\scripts\\confluence.py" search "[검색어]"
python "C:\\Users\\unkno\\tools\\jira-rest\\scripts\\confluence.py" search "[검색어]" --space [SPACE키]
# Confluence — 페이지 읽기
python "C:\\Users\\unkno\\tools\\jira-rest\\scripts\\confluence.py" get [페이지ID]
python "C:\\Users\\unkno\\tools\\jira-rest\\scripts\\confluence.py" get --url "[페이지URL]"
# Confluence — 페이지 작성
python "C:\\Users\\unkno\\tools\\jira-rest\\scripts\\confluence.py" create --space [SPACE키] --title "[제목]" --body "[마크다운내용]"
python "C:\\Users\\unkno\\tools\\jira-rest\\scripts\\confluence.py" create --space [SPACE키] --title "[제목]" --body-file [파일경로]
# Confluence — 페이지 수정
python "C:\\Users\\unkno\\tools\\jira-rest\\scripts\\confluence.py" update [페이지ID] --body "[새내용]"
python "C:\\Users\\unkno\\tools\\jira-rest\\scripts\\confluence.py" update [페이지ID] --append "[추가내용]"


## 작업 시작 시, 티켓 상태 '진행 중' 으로 변경
## 작업 완료 후, 티켓 상태 '검토 중' 으로 변경