import os
import streamlit as st
import uuid
import json
import requests
from markitdown import MarkItDown
from db_manager import save_new_application, get_application_status_by_request, update_application_status
from excel_manager import load_application_questions #διαχείριση ερωτήσεων φόρμας
from langchain_text_splitters import RecursiveCharacterTextSplitter #διαχωρισμός αρχείων σε chunks
from langchain_openai import OpenAIEmbeddings #δημιουργία διανυσμάτων
from langchain_community.vectorstores import FAISS #διανυσματική βάση δεδομένων
from langchain_core.documents import Document

# ============== API KEYS ==============
with open("api_key.txt", "r") as key_file:
    OPENAI_API_KEY = key_file.read().strip()
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
HISTORY_FILE = "chat_history.json"
DOCS_FOLDER = "agent documentation"

# ============== POP-UP ==============
@st.dialog("⚠️️ Σφάλμα Υποβολής")
def error_modal(errors):
    for err in errors:
        st.markdown(f"<p style='color:red; margin-bottom: 5px;'>- {err}</p>", unsafe_allow_html=True)
    if st.button("OK", type="primary", width="stretch"):
        st.rerun()

@st.dialog("✅ Επιτυχής Υποβολή")
def success_modal(request):
    st.markdown(
        f"<p style='color:green; font-size:16px;'>"
        f"Η αίτησή σας καταχωρήθηκε επιτυχώς! <br><br>"
        f"Ο Κωδικός Αίτησής σας είναι: <b>#{request}</b>."
        f"</p>",
        unsafe_allow_html=True
    )
    if st.button("OK", type="primary", width="stretch"):
        st.session_state.form_data = {}
        st.rerun()

# ============== DATA INGESTION, CHUNKING & RAG ==============
@st.cache_resource
def build_knowledge_base(root_folder, index_path="PoC_faiss_index"):
    embeddings = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)

    # load FAISS, if exists
    if os.path.exists(index_path):
        return FAISS.load_local(index_path, embeddings, allow_dangerous_deserialization=True)

    documents = []
    if not os.path.exists(root_folder):
        st.error(f"Ο φάκελος '{root_folder}' δεν βρέθηκε!")
        return None

    md = MarkItDown()

    for root, dirs, files in os.walk(root_folder):
        for filename in files:
            file_path = os.path.join(root, filename)
            if filename.startswith(".") or filename.startswith("~$"):
                continue
            try:
                result = md.convert(file_path)
                documents.append(Document(
                    page_content=result.text_content,
                    metadata={"source": filename}
                ))
            except Exception as e:
                pass

    if not documents:
        return None

    # chunking
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=2000,
        chunk_overlap=300,
        separators=["\n\n", "\n", ".", " ", ""]
    )
    chunks = text_splitter.split_documents(documents)

    # vector database
    vector_store = FAISS.from_documents(chunks, embeddings)
    vector_store.save_local(index_path)

    return vector_store

deddie_vector_store = build_knowledge_base(DOCS_FOLDER)
app_questions = load_application_questions()

# ============== CHAT HISTORY ==============
def load_chat_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass
    return None

def save_chat_history():
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "chats": st.session_state.chats,
            "chat_counter": st.session_state.chat_counter,
            "current_chat_id": st.session_state.current_chat_id
        }, f, ensure_ascii=False, indent=4)

saved_data = load_chat_history()

if "rename_chat_id" not in st.session_state:
    st.session_state.rename_chat_id = None

if "nav_selection" not in st.session_state:
    st.session_state.nav_selection = "👩‍💻 Ψηφιακός Βοηθός"

if "form_data" not in st.session_state:
    st.session_state.form_data = {}

if saved_data and "chats" not in st.session_state:
    st.session_state.chats = saved_data["chats"]
    st.session_state.chat_counter = saved_data["chat_counter"]
    st.session_state.current_chat_id = saved_data["current_chat_id"]

elif "chats" not in st.session_state:
    st.session_state.chat_counter = 1
    default_id = str(uuid.uuid4())
    st.session_state.chats = {
        default_id: {
            "title": "Νέα συνομιλία 1",
            "messages": []
        }
    }
    st.session_state.current_chat_id = default_id

# ============== UI styling (CSS) ==============
st.set_page_config(page_title="RES & CHP Assistant", page_icon="⚡", layout="wide")

st.markdown("""
    <style>
    div.element-container:has(.nav-marker) { display: none !important; }
    div.element-container:has(.nav-active) + div.element-container button {
        background-color: #061A35 !important; color: white !important;
        border: 1px solid #061A35 !important; border-radius: 8px !important; font-weight: normal !important;
    }
    div.element-container:has(.nav-active) + div.element-container button:hover {
        background-color: #092a54 !important; border-color: #092a54 !important; color: white !important;
    }
    div.element-container:has(.nav-inactive) + div.element-container button {
        background-color: transparent !important; color: #061A35 !important;
        border: 1px solid #d1d1d1 !important; border-radius: 8px !important; font-weight: normal !important;
    }
    div.element-container:has(.nav-inactive) + div.element-container button:hover {
        background-color: #E6F0FA !important; border-color: #061A35 !important; color: #061A35 !important;
    }
    </style>
""", unsafe_allow_html=True)

# ============== SIDEBAR ==============
with st.sidebar:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image("RES & CHP Assistant logo.png", width="stretch")
    st.write("")

    is_chat_active = st.session_state.nav_selection == "👩‍💻 Ψηφιακός Βοηθός"
    st.markdown(f'<div class="nav-marker {"nav-active" if is_chat_active else "nav-inactive"}"></div>',
                unsafe_allow_html=True)
    if st.button("👩‍💻 Ψηφιακός Βοηθός", width="stretch"):
        st.session_state.nav_selection = "👩‍💻 Ψηφιακός Βοηθός"
        st.rerun()

    is_form_active = st.session_state.nav_selection == "📝 Πύλη Υποβολής"
    st.markdown(f'<div class="nav-marker {"nav-active" if is_form_active else "nav-inactive"}"></div>',
                unsafe_allow_html=True)
    if st.button("📝 Πύλη Υποβολής", width="stretch"):
        st.session_state.nav_selection = "📝 Πύλη Υποβολής"
        st.rerun()

    st.write("---")

    if st.session_state.nav_selection == "👩‍💻 Ψηφιακός Βοηθός":
        if st.button("➕ Νέα συνομιλία", width="stretch"):
            st.session_state.chat_counter += 1
            new_id = str(uuid.uuid4())
            st.session_state.chats[new_id] = {"title": f"Νέα συνομιλία {st.session_state.chat_counter}", "messages": [],
                                              "last_submitted_request": None, "last_submitted_afm": None}
            st.session_state.current_chat_id = new_id
            st.session_state.rename_chat_id = None
            save_chat_history()
            st.rerun()

        st.write("📁 **Οι συνομιλίες σας:**")

        for chat_id, chat_data in list(st.session_state.chats.items()):
            is_current = (chat_id == st.session_state.current_chat_id)
            col_btn, col_ren, col_del = st.columns([3, 1, 1])

            if col_btn.button(f"💬 {chat_data['title']}", key=f"btn_{chat_id}", width="stretch",
                              type="primary" if is_current else "secondary"):
                st.session_state.current_chat_id = chat_id
                st.session_state.rename_chat_id = None
                save_chat_history()
                st.rerun()

            if col_ren.button("✏️", key=f"ren_{chat_id}", width="stretch"):
                st.session_state.rename_chat_id = chat_id
                st.rerun()

            if col_del.button("🗑️", key=f"del_{chat_id}", width="stretch"):
                if len(st.session_state.chats) > 1:
                    del st.session_state.chats[chat_id]
                    if is_current:
                        st.session_state.current_chat_id = list(st.session_state.chats.keys())[0]
                else:
                    st.session_state.chats[chat_id]["messages"] = []

                save_chat_history()
                st.rerun()

            if st.session_state.rename_chat_id == chat_id:
                new_title = st.text_input("Νέο όνομα:", value=chat_data['title'], key=f"input_{chat_id}",
                                          label_visibility="collapsed")
                if new_title and new_title != chat_data['title']:
                    st.session_state.chats[chat_id]['title'] = new_title
                    st.session_state.rename_chat_id = None
                    save_chat_history()
                    st.rerun()

current_chat = st.session_state.chats[st.session_state.current_chat_id]

# ============== AGENTIC CHAT ==============
if st.session_state.nav_selection == "👩‍💻 Ψηφιακός Βοηθός":
    _, chat_col, _ = st.columns([1.5, 7, 1.5])

    with chat_col:
        st.html(
        "<h2 style='text-align: center; margin-top: 0px; margin-bottom: 0px;'>Ψηφιακός Βοηθός Αιτήσεων ΑΠΕ & ΣΗΘΥΑ⚡</h2>")
        st.html(
        "<p style='text-align: center; color: gray; margin-bottom: 20px;'>Ενημέρωση και καθοδήγηση για τη σύνδεση σταθμών</p>")

        chat_container = st.container()
        with chat_container:
            for message in current_chat["messages"]:
                if message["role"] != "system":
                    with st.chat_message(message["role"]):
                        st.markdown(message["content"])

    if prompt := st.chat_input("Ρωτήστε τον βοηθό..."):
        current_chat["messages"].append({"role": "user", "content": prompt})

        with chat_container:
            with st.chat_message("user"):
                st.markdown(prompt)

        # RAG: Context retrieval
        retrieved_context = ""
        if deddie_vector_store:
            docs = deddie_vector_store.similarity_search(prompt, k=15)
            retrieved_context = "\n\n".join(
                [f"--- ΠΗΓΗ: {doc.metadata.get('source', 'Άγνωστη')} ---\n{doc.page_content}" for doc in docs]
            )

            # Print sources to the terminal
            print("\n" + "-" * 70)
            print(f"ΕΡΩΤΗΜΑ ΧΡΗΣΤΗ: {prompt}")
            print(f"RAG RETRIEVAL - Βρέθηκαν {len(docs)} σχετικά αποσπάσματα.")
            print("Top 3")
            for i, doc in enumerate(docs[:3], 1):
                source_file = doc.metadata.get('source', 'Άγνωστη')
                print(f"\n  [{i}] ΑΡΧΕΙΟ: {source_file}") # Τυπώνουμε το όνομα του αρχείου
                print(f"  ΚΕΙΜΕΝΟ: {doc.page_content.strip()[:200]}...") # Τυπώνουμε τους πρώτους 200 χαρακτήρες
            print("=" * 70 + "\n")

        # Agent tools
        agent_tools = [
            {
                "type": "function",
                "function": {
                    "name": "check_application_status",
                    "description": "Ελέγχει την τρέχουσα κατάσταση της αίτησης. Απαιτείται ταυτοποίηση με ID Αιτήματος και ΑΦΜ.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "appl_request_id": {"type": "integer"},
                            "cust_tax_id": {"type": "string"}
                        },
                        "required": ["appl_request_id", "cust_tax_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "cancel_application",
                    "description": "Ακυρώνει την αίτηση. Απαιτείται ταυτοποίηση με ID Αιτήματος και ΑΦΜ.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "appl_request_id": {"type": "integer"},
                            "cust_tax_id": {"type": "string"}
                        },
                        "required": ["appl_request_id", "cust_tax_id"]
                    }
                }
            }
        ]
        smart_prompt = f"""
                        Είσαι ο επίσημος ψηφιακός βοηθός για θέματα αιτήσεων ΑΠΕ και ΣΗΘΥΑ. Ο ρόλος σου είναι να απαντάς σε ερωτήσεις για αιτήσεις ΑΠΕ και ΣΗΘΥΑ, καθώς και σε τεχνικές ερωτήσεις που συνδέονται με αυτές τις εγκαταστάσεις. Τήρησε αυστηρά τα παρακάτω:
                        1.  Διάβασε προσεκτικά τις "ΠΛΗΡΟΦΟΡΙΕΣ ΑΠΟ ΕΓΓΡΑΦΑ". Αν η απάντηση στην ερώτηση του χρήστη βρίσκεται εκεί, τότε δώσε την αναλυτικά στον χρήστη. Αν ΔΕΝ υπάρχει στα έγγραφα, μην κάνεις εικασίες και ψευδείς παραδοχές! Αντίθετα, παραδέξου το ευγενικά και πρότεινε στον χρήστη να απευθυνθεί στην τηλεφωνική εξυπηρέτηση του αρμόδιου φορέα για περαιτέρω διευκρινίσεις.
                        2.  Πριν εξηγήσεις τα βήματα οποιασδήποτε διαδικασίας (π.χ. νέα αίτηση, επαύξηση, σύνδεση κ.λπ), οφείλεις ΠΑΝΤΑ να ελέγχεις τα αντίστοιχα έγγραφα για:
                                -   Προϋποθέσεις που πρέπει να ικανοποιούνται πριν από αυτήν.
                                -   Περιορισμούς ή κανόνες απόρριψης.
                            Αν εντοπίσεις τα παραπάνω, οφείλεις να ξεκινήσεις την απάντησή σου αναφέροντάς τα ξεκάθαρα. Εξήγησε τη διαδικασία ΜΟΝΟ υπό την προϋπόθεση ότι αυτοί οι κανόνες δεν παραβιάζονται.
                        3.  Για αιτήματα που αφορούν έλεγχο του status της αίτησης, οφείλεις να ζητήσεις Κωδικό Αίτησης και ΑΦΜ, προκειμένου να γίνει ταυτοποίηση. Όταν έχεις και τα δύο, προχώρησε σε κλήση του εργαλείου check_application_status.
                        4.  Για αιτήματα που αφορούν ακύρωση αίτησης, οφείλεις να ζητήσεις Κωδικό Αίτησης και ΑΦΜ, προκειμένου να γίνει ταυτοποίηση. Όταν έχεις και τα δύο, μην δώσεις οδηγίες από τις πληροφορίες των εγγράφων, αλλά προχώρησε σε κλήση του εργαλείου cancel_application (ΌΧΙ του check_application_status).
                        5.  Κράτησε ύφος επαγγελματικό, σοβαρό, άμεσο και φιλικό. Χρησιμοποίησε bullets για δομημένες πληροφορίες. Απόφυγε την επίσημη γλώσσα.
                        6.  Αν η ερώτηση είναι εντελώς άσχετη με τις δραστηριότητες του ΔΕΔΔΗΕ, ενέργεια ή ηλεκτρολογικά, καθοδήγησέ τον χρήστη ευγενικά πίσω στο θέμα μας. Μην απορρίπτεις τεχνικές ερωτήσεις εφόσον οι απαντήσεις τους υπάρχουν στα έγγραφα. Σε απλούς χαιρετισμούς και εισαγωγικές ερωτήσεις, απάντησε φιλικά και σύντομα, χωρίς να παραθέτεις όλο το σκεπτικό σου και επισημαίνοντας τη διαθεσιμότητά σου για βοήθεια σχετικά με τις αιτήσεις.
                        7.  Αν ο χρήστης εκφράσει την επιθυμία να υποβάλει νέα αίτηση ή και να μάθει πώς μπορεί να την υποβάλει, ενημέρωσέ τον με τις πληροφορίες που σου δόθηκαν, αλλά επίσης πρότρεψέ τον ρητά να κάνει κλικ στο κουμπί **'📝 Πύλη Υποβολής'** στο μενού στα αριστερά της οθόνης για να μεταβεί στη φόρμα από την οποία μπορεί να υποβάλλει αίτηση. Τόνισέ του ότι παραμένεις στη διάθεσή του, για διευκρινίσεις σχετικά με τη συμπλήρωση της φόρμας.
                        8.  Απαγορεύεται αυστηρά να κοινοποιείς αρχεία από τα έγγραφα στις συζητήσεις! Αν η πηγή αναφέρει "δείτε το επισυναπτόμενο έγγραφο" κ.λπ, ΜΗΝ δημιουργήσεις συνδέσμους (clickable links) προς αρχεία. Παράθεσε μόνο τα δικαιολογητικά που αναφέρονται ρητά μέσα στο κείμενο των πηγών σου, μορφοποιώντας τα σε λίστα εφόσον χρειάζεται.
                        9.  Χρησιμοποίησε το παρακάτω γλωσσάρι για δική σου διευκόλυνση, αλλά και προκειμένου να δώσεις σχετικές διευκρινίσεις στον χρήστη:
                            ΔΕΔΔΗΕ: Διαχειριστής Ελληνικού Δικτύου Διανομής Ηλεκτρικής Ενέργειας
                            ΑΔΜΗΕ: Ανεξάρτητος Διαχειριστής Μεταφοράς Ηλεκτρικής Ενέργειας
                            ΔΑΠΕΕΠ: Διαχειριστής ΑΠΕ & Εγγυήσεων Προέλευσης
                            ΡΑΕ ή ΡΑΑΕΥ: Ρυθμιστική Αρχή (Αποβλήτων,) Ενέργειας (και Υδάτων)
                            ΔΣ: Διασυνδεδεμένο Σύστημα
                            ΜΔΝ: Μη Διασυνδεδεμένα Νησιά
                            ΑΠΕ: Ανανεώσιμες Πηγές Ενέργειας
                            ΣΗΘΥΑ: Συμπαραγωγή Ηλεκτρισμού και Θερμότητας Υψηλής Απόδοσης
                            ΣΑΗΕ: Σταθμοί Αποθήκευσης Ηλεκτρικής Ενέργειας
                            ΦΒ ή Φ/Β: Φωτοβολταϊκά
                            Α/Γ: Ανεμογεννήτρια
                            Υ/Σ ή ΥΣ: Υποσταθμός
                            ΧΤ: Χαμηλή Τάση
                            ΜΤ: Μέση Τάση
                            ΥΤ: Υψηλή Τάση
                            ΒΚ: Βραχυκύκλωμα
                            ΟΠΣ: Οριστική Προσφορά Σύνδεσης
                            ΣΣ: Σύμβαση Σύνδεσης
                            ΣΕΣΤ: Σύμβαση Λειτουργικής Ενίσχυσης Σταθερής Τιμής (ή γενικά Σύμβαση Λειτουργικής Ενίσχυσης)
                            ΣΕΔΠ: Σύμβαση Ενίσχυσης Διαφορικής Προσαύξησης
                            ΕΠΟ: Έγκριση Περιβαλλοντικών Όρων
                            ΠΠΔ: Πρότυπες Περιβαλλοντικές Δεσμεύσεις

                        ΠΛΗΡΟΦΟΡΙΕΣ ΑΠΟ ΕΓΓΡΑΦΑ (Βρέθηκαν σχετικά αποσπάσματα): 
                        {retrieved_context}
                    """
        api_messages = [{"role": "system", "content": smart_prompt}]

        for msg in current_chat["messages"]:
            if msg.get("content"):
                api_messages.append({"role": msg["role"], "content": msg["content"]})

        # API Request (Agent Decision)
        payload = {
            "model": "gpt-4o-mini",
            "messages": api_messages,
            "tools": agent_tools,
            "tool_choice": "auto"
        }
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {OPENAI_API_KEY}"}
        response = requests.post(OPENAI_URL, json=payload, headers=headers).json()

        # Function Calling
        if "choices" in response and response["choices"][0]["message"].get("tool_calls"):
            tool_call = response["choices"][0]["message"]["tool_calls"][0]
            function_name = tool_call["function"]["name"]
            args = json.loads(tool_call["function"]["arguments"])

            appl_request_id = args.get("appl_request_id")
            cust_tax_id = args.get("cust_tax_id")

            db_info = get_application_status_by_request(appl_request_id)

            # Check application status tool
            if function_name == "check_application_status":
                if db_info and str(db_info.get('cust_tax_id', '')) == str(cust_tax_id):

                    display_status = db_info['appl_current_stage']
                    if display_status == 'ΜΕ ΑΔΥΝΑΜΙΑ ΣΥΝΔΕΣΗΣ' and db_info.get('appl_termination_reason'):
                        display_status += f" ({db_info['appl_termination_reason']})"

                    tool_result = (
                        f"Επιτυχής Ταυτοποίηση! Βρέθηκε η αίτηση #{appl_request_id} στο όνομα {db_info['cust_first_name']} {db_info['cust_last_name']}.\n"
                        f"Τρέχον Στάδιο: {display_status}\n"
                        f"Ημερομηνία Υποβολής: {db_info.get('appl_submitted_on', 'Δ/Υ')}\n"
                    )
                    if db_info.get('appl_initial_offer_on'):
                        tool_result += f"Ημερομηνία Μη Δεσμευτικής Προσφοράς: {db_info['appl_initial_offer_on']}\n"
                    if db_info.get('appl_final_offer_on'):
                        tool_result += f"Ημερομηνία Οριστικής Προσφοράς: {db_info['appl_final_offer_on']}\n"
                    if db_info.get('appl_rejected_on'):
                        tool_result += f"Ημερομηνία Απόρριψης: {db_info['appl_rejected_on']}\n"
                    if db_info.get('appl_signed_on'):
                        tool_result += f"Ημερομηνία Σύμβασης Σύνδεσης: {db_info['appl_signed_on']}\n"
                    if db_info.get('appl_completed_on'):
                        tool_result += f"Ημερομηνία Έναρξης Λειτουργίας: {db_info['appl_completed_on']}\n"
                    if db_info.get('appl_cancelled_on'):
                        tool_result += f"Ημερομηνία Ακύρωσης: {db_info['appl_cancelled_on']}\n"
                else:
                    tool_result = "Ανεπιτυχής Ταυτοποίηση! Δεν βρέθηκε ο παραπάνω συνδυασμός."

            # Cancel application tool
            elif function_name == "cancel_application":
                if not db_info or str(db_info.get('cust_tax_id', '')) != str(cust_tax_id):
                    tool_result = "Ανεπιτυχής ταυτοποίηση! Η ακύρωση απέτυχε."
                elif db_info.get('appl_current_stage') == 'ΜΕ ΑΔΥΝΑΜΙΑ ΣΥΝΔΕΣΗΣ' and db_info.get('appl_cancelled_on'):
                    tool_result = f"Η αίτηση {appl_request_id} έχει ήδη ακυρωθεί στις {db_info.get('appl_cancelled_on')}."
                elif db_info.get('appl_current_stage') == 'ΜΕ ΑΔΥΝΑΜΙΑ ΣΥΝΔΕΣΗΣ' and db_info.get('appl_rejected_on'):
                    tool_result = f"Η αίτηση {appl_request_id} έχει ήδη απορριφθεί στις {db_info.get('appl_rejected_on')}."
                elif db_info.get('appl_current_stage') in ['ΜΕ ΣΥΜΒΑΣΗ ΣΥΝΔΕΣΗΣ', 'ΣΕ ΛΕΙΤΟΥΡΓΙΑ']:
                    tool_result = f"Η αίτηση {appl_request_id} βρίσκεται στο στάδιο '{db_info.get('appl_current_stage')}' και δεν μπορεί πλέον να ακυρωθεί ψηφιακά. Παρακαλώ επικοινωνήστε με την τηλεφωνική εξυπηρέτηση του αρμόδιου φορέα."
                else:
                    update_application_status(appl_request_id, 'cancelled')
                    tool_result = f"Η αίτηση με κωδικό {appl_request_id} ακυρώθηκε επιτυχώς."

            payload_tool_stream = {
                "model": "gpt-4o-mini",
                "messages": api_messages + [
                    {"role": "assistant", "content": None, "tool_calls": [tool_call]},
                    {"role": "tool", "tool_call_id": tool_call["id"], "content": tool_result}
                ],
                "stream": True
            }

            final_payload = {
                "model": "gpt-4o-mini",
                "messages": api_messages + [
                    {"role": "assistant", "content": None, "tool_calls": [tool_call]},
                    {"role": "tool", "tool_call_id": tool_call["id"], "content": tool_result}
                ],
                "stream": True
            }

        else:

            final_payload = {
                "model": "gpt-4o-mini",
                "messages": api_messages,
                "stream": True
            }

        # Server-Sent Events
        with chat_container:
            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                full_response = ""

                res_stream = requests.post(OPENAI_URL, json=final_payload, headers=headers, stream=True)

                for line in res_stream.iter_lines():
                    if line:
                        decoded_line = line.decode("utf-8")
                        if decoded_line.startswith("data: "):
                            data_str = decoded_line[6:]

                            if data_str.strip() == "[DONE]":
                                break

                            try:
                                data = json.loads(data_str)
                                content = data["choices"][0]["delta"].get("content", "")
                                full_response += content
                                message_placeholder.markdown(full_response + "▌")
                            except json.JSONDecodeError:
                               pass

                message_placeholder.markdown(full_response)

        current_chat["messages"].append({"role": "assistant", "content": full_response})
        save_chat_history()
        st.rerun()


# ============== APPLICATION PORTAL ==============
elif st.session_state.nav_selection == "📝 Πύλη Υποβολής":
    _, form_col, _ = st.columns([2, 6, 2])

    with form_col:
        st.html("<h2 style='text-align: center; margin-top: 0px;'>Πύλη Υποβολής Αιτήσεων ⚡</h2>")
        st.write(
            "Συμπληρώστε τα παρακάτω στοιχεία για να καταχωρήσετε την αίτησή σας.\n\n"
            "Για τυχόν απορίες, ο Ψηφιακός Βοηθός είναι στη διάθεσή σας μέσω του Μενού στα αριστερά!"
        )

        st.text_input("Είδος Αιτήματος *", value="Νέα Αίτηση Σύνδεσης", disabled=True)

        for q in app_questions:
            field = q['field']

            if field == "appl_compensation_type":
                continue

            label = q.get('label', field)
            help_text = q['question']

            if q['options']:
                options_list = ["-- Επιλέξτε --"] + q['options']
                saved_val = st.session_state.form_data.get(field, "-- Επιλέξτε --")
                default_idx = options_list.index(saved_val) if saved_val in options_list else 0

                st.session_state.form_data[field] = st.selectbox(
                    f"{label} *",
                    options=options_list,
                    index=default_idx,
                    help=help_text
                )
            else:
                saved_val = st.session_state.form_data.get(field, "")
                st.session_state.form_data[field] = st.text_input(
                    f"{label} *",
                    value=saved_val,
                    help=help_text
                )

        prod_type = st.session_state.form_data.get("cust_producer_type", "")
        if "με αποζημίωση" in prod_type.lower():
            comp_q = next((q for q in app_questions if q['field'] == "appl_compensation_type"), None)

            if comp_q:
                label = comp_q.get('label', "appl_compensation_type")
                options_list = ["-- Επιλέξτε --"] + comp_q['options']
                saved_val = st.session_state.form_data.get("appl_compensation_type", "-- Επιλέξτε --")
                default_idx = options_list.index(saved_val) if saved_val in options_list else 0

                st.session_state.form_data["appl_compensation_type"] = st.selectbox(
                    f"{label} *",
                    options=options_list,
                    index=default_idx,
                    help=comp_q['question']
                )
        else:
            st.session_state.form_data["appl_compensation_type"] = None

        st.markdown(
            "<p style='font-size: 13px; color: #525252; margin-top: 15px;'>"
            "<i>* Όλα τα πεδία που φέρουν αστερίσκο (*) είναι υποχρεωτικά για την υποβολή της αίτησης.</i>"
            "</p>",
            unsafe_allow_html=True
        )

        submitted = st.button("Υποβολή Αίτησης", type="primary", width="stretch")

        # ============== APPLICATION SUBMISSION AND VALIDATION ==============
        if submitted:
            errors = []

            for q in app_questions:
                field = q['field']
                val = st.session_state.form_data.get(field)

                if field == "appl_compensation_type" and val is None:
                    continue

                if not val or val == "-- Επιλέξτε --":
                    errors.append(f"Το πεδίο '{q.get('label', field)}' είναι υποχρεωτικό.")

            afm = str(st.session_state.form_data.get('cust_tax_id', '')).strip()
            if afm and (not afm.isdigit() or len(afm) != 9):
                errors.append("Ο ΑΦΜ πρέπει να αποτελείται από ακριβώς 9 ψηφία.")

            inst_p_str = str(st.session_state.form_data.get("stat_installed_power", "0")).replace(",", ".")
            max_p_str = str(st.session_state.form_data.get("stat_max_power", "0")).replace(",", ".")

            inst_p, max_p = 0.0, 0.0
            try:
                inst_p = float(inst_p_str)
                max_p = float(max_p_str)
                if max_p > inst_p:
                    errors.append(
                        "Η Μέγιστη Ισχύς παραγωγής (kW) δεν μπορεί να υπερβαίνει την Εγκατεστημένη Ισχύ (kW).")
            except ValueError:
                errors.append("Παρακαλώ εισάγετε έγκυρους αριθμούς στα πεδία Ισχύος.")

            if errors:
                error_modal(errors)
            else:
                numeric_chat_id = int(st.session_state.current_chat_id.replace("-", "")[:8], 16)

                request = save_new_application(
                    cust_first_name=st.session_state.form_data.get("cust_first_name"),
                    cust_last_name=st.session_state.form_data.get("cust_last_name"),
                    cust_tax_id=afm,
                    cust_person_type=st.session_state.form_data.get("cust_person_type"),
                    stat_city=st.session_state.form_data.get("stat_city"),
                    cust_producer_type=st.session_state.form_data.get("cust_producer_type"),
                    stat_technology=st.session_state.form_data.get("stat_technology"),
                    stat_installed_power=inst_p,
                    stat_max_power=max_p,
                    appl_compensation_type=st.session_state.form_data.get("appl_compensation_type")
                )
                success_modal(request)
