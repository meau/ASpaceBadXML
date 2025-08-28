import pymysql
import json
import csv
import re
from lxml import etree

# ----------------------------
# Load secrets
# ----------------------------
with open("secrets.json", "r") as f:
    secrets = json.load(f)

db_host = secrets["db_host"]
db_user = secrets["db_user"]
db_password = secrets["db_password"]
db_name = secrets["db_name"]
aspace_base_url = secrets["aspace_base_url"]
output_csv = secrets["output_csv"]

# ----------------------------
# XML validation helper
# ----------------------------
def validate_xml_fragment(text):
    """Validate XML fragment by wrapping in a dummy root element."""
    # Escape stray ampersands
    safe_text = re.sub(r'&(?![a-zA-Z]+;|#\d+;)', '&amp;', text)

    wrapped = f"<root>{safe_text}</root>"
    parser = etree.XMLParser(recover=False)

    try:
        etree.fromstring(wrapped.encode("utf-8"), parser=parser)
        return True, None, text
    except etree.XMLSyntaxError as e:
        error_message = str(e)

        # Ignore any ns2-related namespace errors
        if "ns2" in error_message:
            return True, None, text

        # Highlight problematic part for real errors
        highlighted = text
        try:
            line, col = e.position
            idx = sum(len(l) + 1 for l in text.splitlines()[:line - 1]) + col
            highlighted = text[:idx] + "<<<ERROR HERE>>>" + text[idx:]
        except Exception:
            pass

        return False, error_message, highlighted

# ----------------------------
# Database connection
# ----------------------------
conn = pymysql.connect(
    host=db_host,
    user=db_user,
    password=db_password,
    database=db_name,
    charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor
)

# ----------------------------
# Query archival objects & notes
# ----------------------------
sql = """
SELECT 
    ao.id AS ao_id,
    ao.title AS ao_title,
    ao.root_record_id,
    n.notes AS note_json
FROM archival_object ao
LEFT JOIN note n ON n.archival_object_id = ao.id
"""

# ----------------------------
# Process records
# ----------------------------
with conn.cursor() as cursor, open(output_csv, "w", newline="", encoding="utf-8") as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(["field", "staff_url", "note_type", "subnote_type", "text_with_error", "error_message"])

    cursor.execute(sql)
    rows = cursor.fetchall()

    for row in rows:
        ao_id = row["ao_id"]
        ao_title = row["ao_title"] or ""
        root_record_id = row["root_record_id"]
        note_json = row["note_json"]

        staff_url = f"{aspace_base_url}{root_record_id}#tree::archival_object_{ao_id}"

        # ---- Check archival object title ----
        if "<" in ao_title:
            valid, error, highlighted = validate_xml_fragment(ao_title)
            if not valid:
                writer.writerow([
                    "archival_object.title",
                    staff_url,
                    "",
                    "",
                    highlighted,
                    error
                ])

        # ---- Check notes ----
        if note_json:
            try:
                notes = json.loads(note_json)
                if isinstance(notes, dict):
                    notes = [notes]

                for note in notes:
                    note_type = note.get("type", "")

                    # Top-level note content
                    if "content" in note and isinstance(note["content"], str):
                        text = note["content"]
                        if "<" in text:
                            valid, error, highlighted = validate_xml_fragment(text)
                            if not valid:
                                writer.writerow([
                                    "note.content",
                                    staff_url,
                                    note_type,
                                    "",
                                    highlighted,
                                    error
                                ])

                    # Subnotes
                    if "subnotes" in note and isinstance(note["subnotes"], list):
                        for sub in note["subnotes"]:
                            subnote_type = sub.get("jsonmodel_type", "")
                            text = sub.get("content", "")
                            if isinstance(text, str) and "<" in text:
                                valid, error, highlighted = validate_xml_fragment(text)
                                if not valid:
                                    writer.writerow([
                                        "note.subnote",
                                        staff_url,
                                        note_type,
                                        subnote_type,
                                        highlighted,
                                        error
                                    ])

            except Exception as e:
                print(f"Error parsing notes for AO {ao_id}: {e}")

conn.close()
print(f"✅ Scan complete. Results saved to {output_csv}")
