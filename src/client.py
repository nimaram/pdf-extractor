import streamlit as st
import requests

st.title("Document Extraction App")

token = st.text_input("Enter your API token", type="password")
document_id = st.text_input("Enter Document ID (UUID)")

use_ocr = st.checkbox("Use OCR")
use_advanced = st.checkbox("Use Advanced Extraction")

if st.button("Extract Data") and token and document_id:
    headers = {"Authorization": f"Bearer {token}"}
    params = {"use_ocr": use_ocr, "use_advanced": use_advanced}

    url = f"http://localhost:8000/docs/extract_data/{document_id}"
    response = requests.post(url, headers=headers, params=params)

    if response.status_code == 200:
        data = response.json()
        st.success("Extraction complete!")
        st.json(data)
    else:
        st.error(f"Failed: {response.status_code} {response.text}")
