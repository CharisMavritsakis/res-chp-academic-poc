# End-to-end tests
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from streamlit.testing.v1 import AppTest


# Use Case 1

def test_UseCase1_off_topic_question():
    at = AppTest.from_file("res_chp_assistant.py")
    at.run(timeout=30)

    at.chat_input[0].set_value(
        "Ποια είναι η πρωτεύουσα της Σερβίας;"
    ).run(timeout=30)

    current_chat_id = at.session_state["current_chat_id"]
    messages = at.session_state["chats"][current_chat_id]["messages"]

    final_response = messages[-1]["content"].lower()

    assert messages

    assert "βελιγράδι" not in final_response
    assert (
        "απε" in final_response
        or "σηθυα" in final_response
        or "αίτηση" in final_response
    )


# Use Case 2

def test_UseCase2_information_retrieval():
    at = AppTest.from_file("res_chp_assistant.py")
    at.run(timeout=30)

    at.chat_input[0].set_value(
        "Ποια είναι τα μέτρα περιορισμού του βραχυκυκλώματος σε σταθμούς με σύγχρονες γεννήτριες;"
    ).run(timeout=30)

    current_chat_id = at.session_state["current_chat_id"]
    messages = at.session_state["chats"][current_chat_id]["messages"]

    final_response = messages[-1]["content"].lower()

    assert messages
    assert final_response

    assert (
            "τάση βραχυκύκλωσης" in final_response
            and "επαγωγική" in final_response
            and "μετατροπέα" in final_response
    )


# Use Case 3

def test_UseCase3_new_application_submission():
    at = AppTest.from_file("res_chp_assistant.py")
    at.run(timeout=30)

    at.session_state["nav_selection"] = "📝 Πύλη Υποβολής"
    at.run(timeout=30)

    at.text_input[1].set_value("Δημήτριος")
    at.text_input[2].set_value("Αθανασάκης")
    at.text_input[3].set_value("139845620")
    at.text_input[4].set_value("Ηράκλειο")
    at.text_input[5].set_value("100")
    at.text_input[6].set_value("80")

    # Dropdowns
    at.selectbox[0].select("Φυσικό Πρόσωπο")

    at.selectbox[1].select(
        "Αυτοπαραγωγός Ταυτοχρονισμένου Συμψηφισμού με αποζημίωση ηλεκτρικής ενέργειας"
    )

    at.selectbox[2].select(
        "Φωτοβολταϊκός σταθμός (ΦΒ)"
    )

    at.run(timeout=30)

    at.selectbox[3].select(
        "Απευθείας συμμετοχή στην αγορά"
    )

    at.button[0].click()
    at.run(timeout=30)


# Use Case 4

def test_UseCase4_application_status():

    appl_request_id = 1
    cust_tax_id = "094009834"

    at = AppTest.from_file("res_chp_assistant.py")
    at.run(timeout=30)

    at.chat_input[0].set_value(
        f"Θέλω να ελέγξω την κατάσταση της αίτησής μου. "
        f"Ο κωδικός αίτησης είναι {appl_request_id} και ο ΑΦΜ μου είναι {cust_tax_id}."
    ).run(timeout=30)

    import time
    time.sleep(2)

    current_chat_id = at.session_state["current_chat_id"]
    messages = at.session_state["chats"][current_chat_id]["messages"]

    final_response = messages[-1]["content"].lower()

    assert messages
    assert final_response

    assert str(appl_request_id) in final_response
    assert "υποβολ" in final_response


# Use Case 5

def test_UseCase5_application_cancellation():

    import db_manager

    appl_request_id = 58
    cust_tax_id = "640698386"

    db_manager.update_application_status(
        appl_request_id,
        "non_binding"
    )

    at = AppTest.from_file("res_chp_assistant.py")
    at.run(timeout=30)

    at.chat_input[0].set_value(
        f"Θέλω να ακυρώσω την αίτησή μου. Ο κωδικός αίτησης είναι {appl_request_id} και ο ΑΦΜ μου είναι {cust_tax_id}."
    ).run(timeout=30)

    application = db_manager.get_application_status_by_request(
        appl_request_id
    )

    assert application is not None
    assert application["appl_current_stage"] == "ΜΕ ΑΔΥΝΑΜΙΑ ΣΥΝΔΕΣΗΣ"
    assert application["appl_termination_reason"] == "ΑΚΥΡΩΣΗ"
    assert application["appl_cancelled_on"] is not None
