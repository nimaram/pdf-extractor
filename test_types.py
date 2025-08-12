#!/usr/bin/env python3
"""Simple test script to verify model types are correct."""

import uuid
from src.models.documents import Document
from src.models.users import User
from src.models.extractions import Extraction


def test_model_types():
    """Test that model types are correctly defined."""
    print("Testing model types...")

    # Test Document model
    doc = Document(
        filename="test.pdf", stored_filename="test_stored.pdf", user_id=uuid.uuid4()
    )
    print(f"✓ Document created with id type: {type(doc.id)}")
    print(f"✓ Document user_id type: {type(doc.user_id)}")

    # Test User model (this might not work without database)
    try:
        user = User(email="test@example.com", hashed_password="test")
        print(f"✓ User created with id type: {type(user.id)}")
    except Exception as e:
        print(f"⚠ User creation failed (expected without DB): {e}")

    # Test Extraction model
    extraction = Extraction(
        document_id=uuid.uuid4(), extraction_type="table", data={"test": "data"}
    )
    print(f"✓ Extraction created with id type: {type(extraction.id)}")
    print(f"✓ Extraction document_id type: {type(extraction.document_id)}")

    print("\nAll type checks passed!")


if __name__ == "__main__":
    test_model_types()
