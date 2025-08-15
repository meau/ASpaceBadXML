# DetectBadXMLASpace

**Purpose:**  
This Python script scans an ArchivesSpace MySQL database for malformed XML in **archival object titles** and **note subnotes**. It generates a CSV report showing where bad XML exists so you can fix it in the ArchivesSpace staff interface.

It handles mixed content, nested tags, and namespace attributes, while avoiding false positives from normal XML content.

## Requirements

- Python 3.x
- Python packages: pip install pymysql lxml
- A secrets.json file with your database credentials and output preferences

## Setup

Create secrets.json in the same folder as the script. Example content:

    {
      "db_host": "127.0.0.1",
      "db_user": "your_db_username",
      "db_password": "your_db_password",
      "db_name": "archivesspace_db_name",
      "aspace_base_url": "https://archivessearch.lib.uconn.edu/staff/resources/",
      "output_csv": "bad_xml_report.csv"
    }

* Replace your_db_username, your_db_password, and archivesspace_db_name with your database info.
* aspace_base_url is the base URL for the ArchivesSpace staff interface.
* output_csv is the filename for the CSV report.

## How to Run

1. Open a terminal or command prompt.
2. Navigate to the folder containing the script and secrets.json.
3. Run the script:
   
    python DetectBadXMLASpace.py
   
4. When it finishes, it will print something like:
   
    Report written to bad_xml_report.csv with 15 rows.

5. Open the CSV in Excel, Google Sheets, or another spreadsheet program to review results.

## How It Works

### Archival Object Titles: 

* Scans archival_object.title fields for malformed XML.

### Notes: 

* Scans note.notes JSON arrays, including subnotes and plain-text notes.

### Validation:

* Escapes unescaped & characters to avoid false positives.
* Handles nested XML elements and namespaces.
* Highlights the exact offending tag in bad_xml_snippet with <<< >>>.

### Output CSV Columns:

* record_type – archival_object.title or note.notes
* staff_url – link to the record in ArchivesSpace staff interface
* note_type – type of note (empty for plain-text notes or titles)
* bad_xml_snippet – the malformed XML snippet with highlighting
* error_message – parsing error from lxml

## Notes & Tips

* The script is read-only; it does not modify the database. Fixes can be made by going into the URL in ArchivesSpace and making updates.
* Only records containing < are checked.
* False positives are rare but can occur with unusual characters or complex nested XML.
