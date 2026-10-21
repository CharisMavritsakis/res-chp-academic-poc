import sqlite3
from datetime import datetime

DB_FILE = "res_chp_applications.db"

def get_connection():
    return sqlite3.connect(DB_FILE)

def init_db():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DROP TABLE IF EXISTS applications")

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS applications
                   (
                       appl_request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                       appl_request_type TEXT DEFAULT 'Νέα Αίτηση Σύνδεσης',
                       cust_first_name TEXT,
                       cust_last_name TEXT,
                       cust_tax_id TEXT,
                       cust_person_type TEXT,
                       stat_city TEXT,
                       cust_producer_type TEXT,
                       stat_technology TEXT,
                       stat_installed_power REAL,
                       stat_max_power REAL,
                       appl_compensation_type TEXT,
                       appl_current_stage TEXT DEFAULT 'ΥΠΟΒΟΛΗ ΑΙΤΗΣΗΣ',
                       appl_termination_reason TEXT,
                       appl_submitted_on TEXT,
                       appl_initial_offer_on TEXT,
                       appl_final_offer_on TEXT,
                       appl_rejected_on TEXT,
                       appl_signed_on TEXT,
                       appl_completed_on TEXT,
                       appl_cancelled_on TEXT
                   )
                   """)

    # Triggers for Progress Stages
    stages = [
        ("trg_non_binding", "ΜΕ ΜΗ ΔΕΣΜΕΥΤΙΚΗ ΠΡΟΣΦΟΡΑ", "appl_initial_offer_on"),
        ("trg_final_offer", "ΜΕ ΟΡΙΣΤΙΚΗ ΠΡΟΣΦΟΡΑ", "appl_final_offer_on"),
        ("trg_contract", "ΜΕ ΣΥΜΒΑΣΗ ΣΥΝΔΕΣΗΣ", "appl_signed_on"),
        ("trg_operation", "ΣΕ ΛΕΙΤΟΥΡΓΙΑ", "appl_completed_on")
    ]

    for trigger_name, status_value, date_column in stages:
        cursor.execute(f"""
            CREATE TRIGGER IF NOT EXISTS {trigger_name}
            AFTER UPDATE OF appl_current_stage ON applications
            WHEN NEW.appl_current_stage = '{status_value}'
            BEGIN
                UPDATE applications
                SET {date_column} = datetime('now', 'localtime')
                WHERE appl_request_id = NEW.appl_request_id;
            END;
        """)

    # Triggers for Termination Stages
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_rejection
        AFTER UPDATE OF appl_current_stage, appl_termination_reason ON applications
        WHEN NEW.appl_current_stage = 'ΜΕ ΑΔΥΝΑΜΙΑ ΣΥΝΔΕΣΗΣ' AND NEW.appl_termination_reason = 'ΑΠΟΡΡΙΨΗ'
        BEGIN
            UPDATE applications
            SET appl_rejected_on = datetime('now', 'localtime')
            WHERE appl_request_id = NEW.appl_request_id;
        END;
    """)

    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_cancelled
        AFTER UPDATE OF appl_current_stage, appl_termination_reason ON applications
        WHEN NEW.appl_current_stage = 'ΜΕ ΑΔΥΝΑΜΙΑ ΣΥΝΔΕΣΗΣ' AND NEW.appl_termination_reason = 'ΑΚΥΡΩΣΗ'
        BEGIN
            UPDATE applications
            SET appl_cancelled_on = datetime('now', 'localtime')
            WHERE appl_request_id = NEW.appl_request_id;
        END;
    """)

    conn.commit()
    conn.close()
    print("Η νέα βάση δεδομένων ΑΠΕ αρχικοποιήθηκε!")


def save_new_application(cust_first_name, cust_last_name, cust_tax_id, cust_person_type,
                         stat_city, cust_producer_type, stat_technology, stat_installed_power,
                         stat_max_power, appl_compensation_type=None):

    conn = get_connection()
    cursor = conn.cursor()

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
                   INSERT INTO applications (
                       cust_first_name,
                       cust_last_name,
                       cust_tax_id,
                       cust_person_type,
                       stat_city,
                       cust_producer_type,
                       stat_technology,
                       stat_installed_power,
                       stat_max_power,
                       appl_compensation_type,
                       appl_current_stage,
                       appl_submitted_on
                   )
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   """,
                   (
                       cust_first_name,
                       cust_last_name,
                       cust_tax_id,
                       cust_person_type,
                       stat_city,
                       cust_producer_type,
                       stat_technology,
                       float(stat_installed_power),
                       float(stat_max_power),
                       appl_compensation_type,
                       'ΥΠΟΒΟΛΗ ΑΙΤΗΣΗΣ',
                       current_time
                   ))

    appl_request_id = cursor.lastrowid

    conn.commit()
    conn.close()

    print(
        f"Η αίτηση καταχωρήθηκε επιτυχώς με Κωδικό Αίτησης: {appl_request_id}"
    )

    return appl_request_id


def get_application_status_by_request(appl_request_id):

    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM applications WHERE appl_request_id = ?",
        (int(appl_request_id),)
    )

    row = cursor.fetchone()
    conn.close()

    if row:
        return dict(row)

    return None


def update_application_status(appl_request_id, stage_name):

    conn = get_connection()
    cursor = conn.cursor()

    status_map = {
        'non_binding': (
            'ΜΕ ΜΗ ΔΕΣΜΕΥΤΙΚΗ ΠΡΟΣΦΟΡΑ',
            None
        ),
        'final_offer': (
            'ΜΕ ΟΡΙΣΤΙΚΗ ΠΡΟΣΦΟΡΑ',
            None
        ),
        'contract': (
            'ΜΕ ΣΥΜΒΑΣΗ ΣΥΝΔΕΣΗΣ',
            None
        ),
        'operation': (
            'ΣΕ ΛΕΙΤΟΥΡΓΙΑ',
            None
        ),
        'rejection': (
            'ΜΕ ΑΔΥΝΑΜΙΑ ΣΥΝΔΕΣΗΣ',
            'ΑΠΟΡΡΙΨΗ'
        ),
        'cancelled': (
            'ΜΕ ΑΔΥΝΑΜΙΑ ΣΥΝΔΕΣΗΣ',
            'ΑΚΥΡΩΣΗ'
        )
    }

    if stage_name in status_map:
        new_status, term_reason = status_map[stage_name]

        query = """
            UPDATE applications
            SET appl_current_stage = ?, appl_termination_reason = ?
            WHERE appl_request_id = ?
        """

        cursor.execute(
            query,
            (new_status, term_reason, int(appl_request_id))
        )

        conn.commit()

        reason_text = (
            f" (Αιτία: {term_reason})"
            if term_reason
            else ""
        )

        print(
            f"Η αίτηση {appl_request_id} ενημερώθηκε σε: "
            f"{new_status}{reason_text}"
        )

    conn.close()

if __name__ == "__main__":
    init_db()
