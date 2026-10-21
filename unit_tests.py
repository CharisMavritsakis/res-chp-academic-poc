import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db_manager

def setup_test_db(tmp_path):

    test_db = tmp_path / "test_database.db"

    db_manager.DB_FILE = str(test_db)

    db_manager.init_db()

def create_test_application():
    return db_manager.save_new_application(
        cust_first_name="Δημήτριος",
        cust_last_name="Αθανασάκης",
        cust_tax_id="139845620",
        cust_person_type="Φυσικό Πρόσωπο",
        stat_city="Ηράκλειο",
        cust_producer_type="Αυτοπαραγωγός Ταυτοχρονισμένου Συμψηφισμού με αποζημίωση ηλεκτρικής ενέργειας",
        stat_technology="Φωτοβολταϊκός σταθμός (ΦΒ)",
        stat_installed_power=100,
        stat_max_power=80,
        appl_compensation_type="Απευθείας συμμετοχή στην αγορά"
    )

# Use Case 3

def test_UseCase3_save_and_get_application(tmp_path):

    setup_test_db(tmp_path)

    appl_request_id = create_test_application()

    application = db_manager.get_application_status_by_request(
        appl_request_id
    )

    assert application is not None
    assert application["appl_request_id"] == appl_request_id
    assert application["cust_first_name"] == "Δημήτριος"
    assert application["cust_last_name"] == "Αθανασάκης"
    assert application["cust_tax_id"] == "139845620"
    assert application["appl_current_stage"] == "ΥΠΟΒΟΛΗ ΑΙΤΗΣΗΣ"
    assert application["appl_submitted_on"] is not None


# Use Case 4

def test_UseCase4_get_nonexistent_application(tmp_path):

    setup_test_db(tmp_path)

    application = db_manager.get_application_status_by_request(
        999999
    )

    assert application is None


# Use Case 5

def test_UseCase5_cancel_application(tmp_path):
    setup_test_db(tmp_path)

    appl_request_id = create_test_application()

    db_manager.update_application_status(
        appl_request_id,
        "cancelled"
    )

    application = db_manager.get_application_status_by_request(
        appl_request_id
    )

    assert application is not None
    assert application["appl_current_stage"] == "ΜΕ ΑΔΥΝΑΜΙΑ ΣΥΝΔΕΣΗΣ"
    assert application["appl_termination_reason"] == "ΑΚΥΡΩΣΗ"
    assert application["appl_cancelled_on"] is not None