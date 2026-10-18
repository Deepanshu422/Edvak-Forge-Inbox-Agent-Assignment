import pytest
from src.domain.store import ClinicStore
from src.domain.policies import verify_patient_identity, check_refill_eligibility
from src.domain.scheduling import get_available_slots, is_provider_on_leave

@pytest.fixture
def store():
    return ClinicStore(data_dir="data")

def test_caregiver_verification(store):
    # Sofia Rossi (P009) contacted by her mother Anna Rossi (555-0109)
    res = verify_patient_identity(store, name="Anna Rossi", contact="555-0109")
    assert res["verified"] is True
    assert res["patient_id"] == "P009"

def test_unverified_contact_and_transposed_dob(store):
    # Robert Chen (P002) - email unknown, stated DOB incorrect
    res = verify_patient_identity(store, name="Robert Chen", contact="rchen.new@example.org", stated_dob="1971-11-20")
    assert res["verified"] is False
    assert "disclose_phi" in res["forbidden_actions"]

def test_refill_controlled_substance(store):
    patient = store.get_patient_by_id("P006")  # Marcus Bell
    med = next(m for m in store.get_medications_for_patient("P006") if "Alprazolam" in m.medication)
    res = check_refill_eligibility(patient, med)
    assert res["eligible"] is False
    assert res["required_action"] == "route_to_provider"
    assert "prepare_refill_for_approval" in res["forbidden_actions"]

def test_refill_too_early(store):
    patient = store.get_patient_by_id("P015")  # Fatima Hassan
    med = next(m for m in store.get_medications_for_patient("P015") if "Omeprazole" in m.medication)
    res = check_refill_eligibility(patient, med)
    assert res["eligible"] is False
    assert res["required_action"] == "refill_too_early"
    assert res["earliest_date"] == "2026-11-17"

def test_provider_leave_blocks_slots(store):
    # Dr. Okafor is on leave Nov 16–20, 2026
    assert is_provider_on_leave(store, "OKAFOR", "2026-11-18") is True
    res = get_available_slots(store, "OKAFOR", "2026-11-18", "follow_up")
    assert res["available"] is False
    assert "leave" in res["reason"]