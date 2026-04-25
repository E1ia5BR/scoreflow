import zipfile
import re

try:
    with zipfile.ZipFile('scoreflow-spec.docx', 'r') as zf:
        xml = zf.read('word/document.xml').decode('utf-8')
        text = re.sub(r'<w:p\b[^>]*>', '\n', xml)
        text = re.sub(r'<[^>]+>', '', text)
        with open('scoreflow-spec.txt', 'w', encoding='utf-8') as f:
            f.write(text)
    print("Success")
except Exception as e:
    print("Error:", e)
