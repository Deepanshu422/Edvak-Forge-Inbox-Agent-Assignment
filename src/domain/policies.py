from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from .store import ClinicStore
from .schemas import Patient, Medication

# As defined in problem statement
TODAY_STR = "2026-11-09"
TODAY = datetime.strptime(TODAY_STR, "%Y-%m-%d")


def verify_patient_identity(store: ClinicStore, name: str, contact: Optional[str] = None, stated_dob: Optional[str] = None, body: Optional[str] = None) -> Dict[str, Any]:
    """Verifies a patient or caregiver based on clinic privacy policies."""
    name_clean = (name or "").strip().lower()
    contact_clean = (contact or "").strip().lower()
    body_clean = (body or "").lower()

    # check patient name
    matched_patient = next(
        (p for p in store.patients.values() if p.name.lower() == name_clean), 
        None
    )

    # Match via authorised caregiver (by caregiver name OR caregiver phone)
    if not matched_patient:
        matched_patient = next(
            (p for p in store.patients.values() 
             if p.authorised_caregiver and (
                 p.authorised_caregiver.name.lower() == name_clean or
                 (contact_clean and p.authorised_caregiver.phone.lower() == contact_clean)
             )), 
            None
        )
        if matched_patient:
            cg = matched_patient.authorised_caregiver
            if contact_clean and cg.phone.lower() == contact_clean:
                return {
                    "verified": True,
                    "patient_id": matched_patient.id,
                    "patient_name": matched_patient.name,
                    "primary_provider": matched_patient.primary_provider,
                    "preferred_language": matched_patient.preferred_language,
                    "reason": f"Verified via authorised caregiver ({cg.name}, {cg.relationship})."
                }

    # Check if an existing patient's full name or first name + caregiver phone is mentioned in the message body
    if not matched_patient and body_clean:
        matched_patient = next(
            (p for p in store.patients.values() if p.name.lower() in body_clean),
            None
        )
        if matched_patient:
            # Unauthorized third-party asking about a patient in the body (e.g., M027 "my wife Grace Park")
            return {
                "verified": False,
                "patient_id": matched_patient.id,
                "patient_name": matched_patient.name,
                "reason": f"Sender '{name}' is an unauthorised third party asking about patient {matched_patient.name}.",
                "required_action": "decline_disclosure",
                "forbidden_actions": ["disclose_phi"]
            }

    if not matched_patient:
        return {
            "verified": False,
            "patient_id": None,
            "reason": "Sender not found in patient or caregiver records (possible new patient or spam).",
            "forbidden_actions": ["disclose_phi"]
        }

    # stated_dob is explicitly provided and mismatches -> fail verification 
    if stated_dob and stated_dob != matched_patient.dob:
        return {
            "verified": False,
            "patient_id": matched_patient.id,
            "reason": f"Stated DOB ({stated_dob}) does not match record ({matched_patient.dob}) and contact is unverified.",
            "required_action": "request_verification",
            "forbidden_actions": ["disclose_phi"]
        }

    # verify via contact on file (patient phone/email OR caregiver phone) or matching DOB
    contact_matches = contact_clean and (
        contact_clean == matched_patient.phone.lower() or 
        contact_clean == matched_patient.email.lower() or
        (matched_patient.authorised_caregiver and contact_clean == matched_patient.authorised_caregiver.phone.lower())
    )
    dob_matches = stated_dob and stated_dob == matched_patient.dob

    if contact_matches or dob_matches:
        return {
            "verified": True,
            "patient_id": matched_patient.id,
            "patient_name": matched_patient.name,
            "primary_provider": matched_patient.primary_provider,
            "last_visit": matched_patient.last_visit,
            "preferred_language": matched_patient.preferred_language,
            "reason": "Verified via contact/DOB on file."
        }

    return {
        "verified": False,
        "patient_id": matched_patient.id,
        "reason": "Name matched, but contact/DOB verification failed.",
        "required_action": "request_verification",
        "forbidden_actions": ["disclose_phi"]
    }


def check_refill_eligibility(patient: Patient, medication: Medication) -> dict[str, Any]:
    """Evaluates the 5-gate refill policy deterministically."""

    # controlled substance check
    if medication.controlled_schedule:

        return {
            "eligible": False,
            "reason": f"Controlled substance ({medication.controlled_schedule}).",
            "required_action": "route_to_provider",
            "forbidden_actions": ["prepare_refill_for_approval"]
        }

    # visited within last 12 months or not
    last_visit_date = datetime.strptime(patient.last_visit, "%Y-%m-%d")
    months_since_visit = (TODAY - last_visit_date).days / 30.44

    if months_since_visit > 12:
        return {
            "eligible": False,
            "reason": f"Patient not seen in over 12 months (Last visit: {patient.last_visit}).",
            "required_action": "refill_needs_visit",
            "forbidden_actions": ["prepare_refill_for_approval"]
        }

    # refills remaining
    if medication.refills_remaining <= 0:
        return {
            "eligible": False,
            "reason": "Zero refills remaining.",
            "required_action": "route_to_provider",
            "forbidden_actions": ["prepare_refill_for_approval"]
        }

    # check for 7 days of run-out for current supply for refills
    last_filled = datetime.strptime(medication.last_filled, "%Y-%m-%d")
    run_out_date = last_filled + timedelta(days=medication.days_supply)
    earliest_refill_date = run_out_date - timedelta(days=7)

    if TODAY < earliest_refill_date:
        return {
            "eligible": False,
            "reason": f"Too early. Earliest request date is {earliest_refill_date.strftime('%Y-%m-%d')}.",
            "required_action": "refill_too_early",
            "forbidden_actions": ["prepare_refill_for_approval"],
            "earliest_date": earliest_refill_date.strftime('%Y-%m-%d')
        }

    # Eligible
    return {
        "eligible": True,
        "reason": "Meets all criteria.",
        "required_action": "prepare_refill_for_approval",
        "target_queue": "provider_refills"
    }