import random
import sqlite3
import sqlite3
from datetime import datetime, timedelta
from db_manager import save_new_application, update_application_status

DB_FILE = "res_chp_applications.db"

def generate_mock_data(num_records=24):
    first_names = ["Γεώργιος", "Μαρία", "Κωνσταντίνος", "Ελένη", "Νικόλαος", "Ανδρέας", "Δήμητρα", "Στυλιανή", "Σοφία",
                   "Αναστασία", "Ιωάννης", "Παναγιώτα", "Λουκάς", "Βασιλική", "Πέτρος", "Ευγενία"]
    last_names = ["Δημητρίου", "Γεωργίου", "Νικολάου", "Κωνσταντίνου", "Δημητρίου", "Αντωνίου", "Παναγιώτου",
                  "Δελόγλου", "Στεφάνου", "Καράογλου", "Παπάζογλου"]
    cities = ["Αθήνα", "Θεσσαλονίκη", "Πάτρα", "Ηράκλειο", "Λάρισα", "Βόλος", "Ιωάννινα", "Τρίκαλα", "Χαλκίδα",
              "Σέρρες", "Καβάλα", "Ρόδος", "Λαμία"]
    person_types = ["Φυσικό Πρόσωπο", "Νομικό Πρόσωπο", "Ενεργειακή Κοινότητα (Ε.Κοιν.)",
                    "Ενεργειακή Κοινότητα Πολιτών (Ε.Κ.Π.)", "Κοινότητα Ανανεώσιμης Ενέργειας (Κ.Α.Ε.)", "Άλλη μορφή"]
    producer_types = ["Παραγωγός με αποζημίωση ηλεκτρικής ενέργειας",
                      "Αυτοπαραγωγός Ταυτοχρονισμένου Συμψηφισμού με αποζημίωση ηλεκτρικής ενέργειας",
                      "Αυτοπαραγωγός Ταυτοχρονισμένου Συμψηφισμού χωρίς αποζημίωση ηλεκτρικής ενέργειας",
                      "Αυτοπαραγωγός Εικονικού Ταυτοχρονισμένου Συμψηφισμού με αποζημίωση ηλεκτρικής ενέργειας",
                      "Αυτοπαραγωγός Εικονικού Ταυτοχρονισμένου Συμψηφισμού χωρίς αποζημίωση ηλεκτρικής ενέργειας"]
    techs = ["Φωτοβολταϊκός σταθμός (ΦΒ)", "Υδροηλεκτρικός σταθμός (ΥΗΣ)", "ΣΗΘΥΑ με Φυσικό Αέριο (ΣΗΘΥΑ)",
             "Ηλιοθερμικός σταθμός (Η)", "Γεωθερμικός σταθμός (Γ)", "Σταθμός Βιομάζας/Βιορευστών (ΒΙΟΜ)",
             "Σταθμός Βιοαερίου (ΒΙΟΑ)", "Αιολικός σταθμός (ΑΠ)"]
    comp_types = ["Αποζημίωση με λειτουργική ενίσχυση", "Απευθείας συμμετοχή στην αγορά"]

    stages = ['non_binding', 'final_offer', 'rejection', 'contract', 'operation', 'cancelled']
    success_path = ['non_binding', 'final_offer', 'contract', 'operation']

    date_columns = {
        'non_binding': 'appl_initial_offer_on',
        'final_offer': 'appl_final_offer_on',
        'contract': 'appl_signed_on',
        'operation': 'appl_completed_on',
        'rejection': 'appl_rejected_on',
        'cancelled': 'appl_cancelled_on'
    }

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    print(f"Ξεκινάει η δημιουργία {num_records} εικονικών εγγραφών με ρεαλιστικές ημερομηνίες...\n")

    for i in range(num_records):
        fname = random.choice(first_names)
        lname = random.choice(last_names)
        tax_id = str(random.randint(1, 999999999)).zfill(9)
        ptype = random.choice(person_types)
        city = random.choice(cities)
        prod_type = random.choice(producer_types)
        tech = random.choice(techs)
        inst_power = round(random.uniform(5.0, 500.0), 2)
        max_power = round(inst_power - random.uniform(0.0, inst_power * 0.15), 2)
        comp_type = random.choice(comp_types) if "με αποζημίωση" in prod_type.lower() else None

        request = save_new_application(fname, lname, tax_id, ptype, city, prod_type, tech, inst_power, max_power,
                                      comp_type)

        start_days_ago = random.randint(150, 300)
        current_sim_date = datetime.now() - timedelta(days=start_days_ago)

        cursor.execute("UPDATE applications SET appl_submitted_on = ? WHERE appl_request_id = ?",
                       (current_sim_date.strftime("%Y-%m-%d %H:%M:%S"), request))
        conn.commit()

        if random.random() > 0.3:
            target_stage = random.choice(stages)

            if target_stage in ['rejection', 'cancelled']:
                steps_before_fail = random.randint(0, 2)
                for step in range(steps_before_fail):
                    stage_name = success_path[step]
                    update_application_status(request, stage_name)

                    added_days = random.randint(5, 15)
                    current_sim_date += timedelta(days=added_days, hours=random.randint(1, 5))

                    col_name = date_columns[stage_name]
                    cursor.execute(f"UPDATE applications SET {col_name} = ? WHERE appl_request_id = ?",
                                   (current_sim_date.strftime("%Y-%m-%d %H:%M:%S"), request))
                    conn.commit()

                # Μετάβαση στο στάδιο αποτυχίας
                update_application_status(request, target_stage)
                current_sim_date += timedelta(days=random.randint(5, 15))
                col_name = date_columns[target_stage]
                cursor.execute(f"UPDATE applications SET {col_name} = ? WHERE appl_request_id = ?",
                               (current_sim_date.strftime("%Y-%m-%d %H:%M:%S"), request))
                conn.commit()

            else:
                target_index = success_path.index(target_stage)
                for step in range(target_index + 1):
                    stage_name = success_path[step]
                    update_application_status(request, stage_name)

                    # Προσθέτουμε 5 έως 15 ημέρες
                    added_days = random.randint(5, 15)
                    current_sim_date += timedelta(days=added_days, hours=random.randint(1, 5))

                    # Overwrite
                    col_name = date_columns[stage_name]
                    cursor.execute(f"UPDATE applications SET {col_name} = ? WHERE appl_request_id = ?",
                                   (current_sim_date.strftime("%Y-%m-%d %H:%M:%S"), request))
                    conn.commit()

        print(f"Εγγραφή {i + 1}/{num_records} ολοκληρώθηκε.")

    conn.close()
    print(f"\nΗ δημιουργία των {num_records} εγγραφών ολοκληρώθηκε!")

if __name__ == "__main__":
    generate_mock_data(24)
