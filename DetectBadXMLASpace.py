import pymysql
import json
import csv
import re
from lxml import etree

# ====== LOAD SECRETS ======
with open("secrets.json", "r", encoding="utf-8") as f:
    secrets = json.load(f)

DB_HOST = secrets["db_host"]
DB_USER = secrets["db_user"]
DB_PASSWORD = secrets["db_password"]
DB_NAME = secrets["db_name"]
ASPACE_BASE_URL = secrets["aspace_base_url"]
OUTPUT_CSV = secrets["output_csv"]

# ====== VALIDATION FUNCTION ======
def validate_xml_fragment(text):
    """
    Validate XML fragment including nested tags.
    Escapes unescaped & characters.
    Wraps in a dummy root with a namespace to handle attributes like ns2:type.
    Highlights entire malformed tag if an error occurs.
    """
    if not text or "<" not in text:
        return True, "", text

    try:
        # Escape & safely
        safe_text = re.sub(r'&(?![a-zA-Z]+;|#\d+;)', '&amp;', text)
        # Wrap whole fragment in dummy root with namespace
        root_wrap = f'<root xmlns:ns2="http://example.com">{safe_text}</root>'
        etree.fromstring(root_wrap)
        return True, "", text

    except etree.XMLSyntaxError as e:
        error_msg = str(e)
        highlight_text = text

        # Attempt to mark entire offending tag
        try:
            # Find first opening '<' before the error column
            col_pos = None
            for part in error_msg.split(","):
                part = part.strip()
                if part.startswith("column "):
                    col_pos = int(part.replace("column ", "").strip())
                    break
            if col_pos and 0 < col_pos <= len(text):
                start = text.rfind('<', 0, col_pos)
                end = text.find('>', col_pos)
                if start != -1 and end != -1:
                    highlight_text = text[:start] + "<<<" + text[start:end+1] + ">>>" + text[end+1:]
                else:
                    # fallback: mark single character
                    highlight_text = text[:col_pos-1] + "<<<" + text[col_pos-1] + ">>>" + text[col_pos:]
        except Exception:
            pass

        return False, error_msg, highlight_text

# ====== CONNECT TO DATABASE ======
conn = pymysql.connect(
    host=DB_HOST,
    user=DB_USER,
    password=DB_PASSWORD,
    database=DB_NAME,
    charset="utf8mb4"
)
cursor = conn.cursor()

results = []

# ====== 1. Check archival_object.title ======
cursor.execute("""
    SELECT id, root_record_id, title
    FROM archival_object
    WHERE title LIKE '%%<%%'
""")
for ao_id, root_id, title in cursor.fetchall():
    valid, error, highlighted = validate_xml_fragment(title)
    if not valid:
        staff_url = f"{ASPACE_BASE_URL}{root_id}#tree::archival_object_{ao_id}"
        results.append({
            "record_type": "archival_object.title",
            "staff_url": staff_url,
            "note_type": "",
            "bad_xml_snippet": highlighted,
            "error_message": error
        })

# ====== 2. Check all subnotes in note.notes ======
cursor.execute("""
    SELECT n.notes, ao.id, ao.root_record_id
    FROM note n
    JOIN archival_object ao ON ao.id = n.archival_object_id
    WHERE n.notes LIKE '%%<%%'
""")
for notes_blob, ao_id, root_id in cursor.fetchall():
    try:
        notes_json = json.loads(notes_blob)
    except Exception as e:
        staff_url = f"{ASPACE_BASE_URL}{root_id}#tree::archival_object_{ao_id}"
        results.append({
            "record_type": "note.notes",
            "staff_url": staff_url,
            "note_type": "",
            "bad_xml_snippet": "",
            "error_message": f"Invalid JSON: {e}"
        })
        continue

    for note in notes_json:
        # Handle note as dict
        if isinstance(note, dict):
            note_type = note.get("type", "")
            subnotes = note.get("subnotes", [])
            for sub in subnotes:
                content = sub.get("content", "")
                valid, error, highlighted = validate_xml_fragment(content)
                if not valid:
                    staff_url = f"{ASPACE_BASE_URL}{root_id}#tree::archival_object_{ao_id}"
                    results.append({
                        "record_type": "note.notes",
                        "staff_url": staff_url,
                        "note_type": note_type,
                        "bad_xml_snippet": highlighted,
                        "error_message": error
                    })
        # Handle note as plain string
        elif isinstance(note, str):
            content = note
            valid, error, highlighted = validate_xml_fragment(content)
            if not valid:
                staff_url = f"{ASPACE_BASE_URL}{root_id}#tree::archival_object_{ao_id}"
                results.append({
                    "record_type": "note.notes",
                    "staff_url": staff_url,
                    "note_type": "",
                    "bad_xml_snippet": highlighted,
                    "error_message": error
                })

# ====== WRITE OUTPUT ======
with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=["record_type", "staff_url", "note_type", "bad_xml_snippet", "error_message"]
    )
    writer.writeheader()
    writer.writerows(results)

print(f"Report written to {OUTPUT_CSV} with {len(results)} rows.")

cursor.close()
conn.close()
