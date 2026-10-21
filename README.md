# res-chp-academic-poc
Source code for a RAG-based digital assistant for RES and CHP applications. Developed for my Master's thesis at the Techno-Economic Systems program.

How to run the project locally:

1. Clone the repository.

2. Create a virtual environment and activate it.

3. Install the dependencies: pip install -r requirements.txt

4. Create a file named api_key.txt in the root directory and paste your OpenAI API Key inside it.

5. Initialize the database by running: python db_manager.py

6. (Optional) Populate the database with mock data by running: python new_rows_generator.py

7. Run the app: streamlit run res_chp_assistant.py
