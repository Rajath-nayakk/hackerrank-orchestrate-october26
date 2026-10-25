import zipfile
import os

zip_path = r"c:\Users\Rajath Nayak\OneDrive\Desktop\hackerrank-orchestrate-october26\code.zip"

with zipfile.ZipFile(zip_path, 'r') as zf:
    namelist = zf.namelist()
    print(f"Total entries in code.zip: {len(namelist)}")
    
    prohibited_keywords = ["dataset", ".venv", "venv", "__pycache__", ".git", ".DS_Store", ".zip", ".tar", ".gz"]
    prohibited_found = []
    
    for name in namelist:
        lower = name.lower()
        for kw in prohibited_keywords:
            if kw in lower and not (kw == ".zip" and lower.endswith("code.zip")):
                # check if nested archive
                if any(lower.endswith(ext) for ext in [".zip", ".tar", ".gz", ".tgz", ".7z", ".rar"]):
                    prohibited_found.append((name, "nested archive"))
                elif "dataset" in lower:
                    prohibited_found.append((name, "dataset file"))
                elif "__pycache__" in lower:
                    prohibited_found.append((name, "pycache"))
                elif ".venv" in lower or "venv" in lower:
                    prohibited_found.append((name, "virtualenv"))
                    
    print("Prohibited files found:", prohibited_found)
    
    required_files = [
        "README.md",
        "code/main.py",
        "code/auditor.py",
        "code/classifier.py",
        "code/evidence_loader.py",
        "code/identity.py",
        "code/evaluation/evaluation_report.md",
        "code/evaluation/usage_report.md"
    ]
    
    normalized_names = [n.replace("\\", "/") for n in namelist]
    missing_required = []
    for req in required_files:
        if req not in normalized_names:
            missing_required.append(req)
            
    print("Missing required files:", missing_required)
    print("Sample of files in archive:")
    for n in sorted(normalized_names)[:20]:
        print(" ", n)

