import pandas as pd
import os

EXCEL_FILE = "application_fields.xlsx"

def load_application_questions():

    if not os.path.exists(EXCEL_FILE):
        print(f"Σφάλμα: Το αρχείο '{EXCEL_FILE}' δεν βρέθηκε!")
        return []

    df = pd.read_excel(EXCEL_FILE)

    questions_list = []

    for index, row in df.iterrows():
        field_name = str(row['Field']).strip()
        question_text = str(row['Question']).strip()
        label_text = str(row['Label']).strip() if pd.notna(row['Label']) else field_name
        options_raw = row['Options']

        if pd.notna(options_raw) and str(options_raw).strip() != "":
            options_list = [opt.strip() for opt in str(options_raw).split(",")]
        else:
            options_list = None

        questions_list.append({
            "field": field_name,
            "question": question_text,
            "label": label_text,
            "options": options_list
        })

    return questions_list