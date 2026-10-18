import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from src.domain.schemas import Appointment
from src.domain.store import ClinicStore
from src.domain.policies import verify_patient_identity, check_refill_eligibility
from src.domain.scheduling import get_available_slots

# A lightweight clinical map for known brand-to-generic
BRAND_TO_GENERIC_MAP = {
    "xanax": "alprazolam",
    "lipitor": "atorvastatin",
    "glucophage": "metformin",
    "zoloft": "sertraline",
    "ambien": "zolpidem",
    "norvasc": "amlodipine",
    "lexapro": "escitalopram",
    "coumadin": "warfarin",
    "aricept": "donepezil",
    "zestril": "lisinopril",
    "prinivil": "lisinopril"
}

class MapleMCPServer:

    def __init__(self, data_dir: str = "data"):
        self.store = ClinicStore(data_dir=data_dir)

    def tool_verify_patient(self, name: str, contact: Optional[str] = None, stated_dob: Optional[str] = None, body: Optional[str] = None) -> Dict[str, Any]:
        return verify_patient_identity(self.store, name, contact, stated_dob, body)
    
    def tool_get_patient_appointments(self, patient_id: str) -> List[Dict[str, Any]]:
        """Retrieves all active appointments for a verified patient."""
        return [
            appt.model_dump() 
            for appt in self.store.appointments.values() 
            if appt.patient_id == patient_id and appt.status == "booked"
        ]
    
    
    def tool_check_refill(self, patient_id: str, medication_name: str) -> Dict[str, Any]:
        patient = self.store.get_patient_by_id(patient_id)
        if not patient:
            return {"error" : "Patient not found."}

        patient_meds = self.store.get_medications_for_patient(patient_id)

        search_term = medication_name.lower().strip()
        
        # checking if user's term present in map

        if search_term in BRAND_TO_GENERIC_MAP:
            search_term = BRAND_TO_GENERIC_MAP[search_term]

        medication = next((m for m in patient_meds if search_term in m.medication.lower()), None)

        if not medication:
            return {
                "error": f"Medication '{medication_name}' not found on patient profile."
            }

        return check_refill_eligibility(patient, medication)

    def tool_find_slots(self, provider_id: str, date_str: str, visit_type: str) -> Dict[str, Any]:

        return get_available_slots(self.store, provider_id, date_str, visit_type)

    def tool_book_appointment(self, patient_id: str, provider_id: str, date_str: str, start_time: str, visit_type: str) -> Dict[str, Any]:
        
        # verifying slot is still open before committing

        slots_check = self.tool_find_slots(provider_id, date_str, visit_type)
        if start_time not in slots_check.get("slots", []):
            return {
                "success": False, 
                "reason": slots_check.get("reason", "Requested slot is not available."),
                "required_action": "offer_alternatives",
                "available_slots": slots_check.get("slots", [])
            }
        

        duration_mins = self.store.clinic_info["visit_types"].get(visit_type, 20)
        start_dt = datetime.strptime(start_time, "%H:%M")
        end_dt = start_dt + timedelta(minutes=duration_mins)
        end_time = end_dt.strftime("%H:%M")

        new_id = f"A{uuid.uuid4().hex[:4].upper()}"
        new_appt = Appointment(
            id=new_id,
            patient_id=patient_id,
            provider=provider_id,
            date=date_str,
            start=start_time,
            end=end_time,
            visit_type=visit_type,
            status="booked"
        )
        self.store.add_appointment(new_appt)

        return {
            "success": True,
            "appointment_id": new_id,
            "action_taken": "book_appointment",
            "details": f"Booked {visit_type} with {provider_id} on {date_str} from {start_time} to {end_time}."
        }

    def tool_reschedule_appointment(self, appointment_id: str, new_date: str, new_start: str, provider_id: Optional[str] = None) -> Dict[str, Any]:
        """Reschedules an existing appointment to a new date and time."""
        appt = self.store.appointments.get(appointment_id)
        if not appt:
            return {"success": False, "error": f"Appointment {appointment_id} not found."}

        target_provider = provider_id or appt.provider
        slots_check = self.tool_find_slots(target_provider, new_date, appt.visit_type)
        if new_start not in slots_check.get("slots", []):
            return {
                "success": False,
                "reason": "Requested reschedule slot is not available.",
                "available_slots": slots_check.get("slots", [])
            }

        duration_mins = self.store.clinic_info["visit_types"].get(appt.visit_type, 20)
        start_dt = datetime.strptime(new_start, "%H:%M")
        end_dt = start_dt + timedelta(minutes=duration_mins)
        end_time = end_dt.strftime("%H:%M")

        self.store.update_appointment(appointment_id, new_date, new_start, end_time)
        return {
            "success": True,
            "action_taken": "reschedule_appointment",
            "details": f"Rescheduled {appointment_id} to {new_date} at {new_start}."
        }

    def tool_cancel_appointment(self, appointment_id: str) -> Dict[str, Any]:
        """Cancels an existing appointment in the store."""
        appt = self.store.appointments.get(appointment_id)
        if not appt:
            return {"success": False, "error": f"Appointment {appointment_id} not found."}
        
        self.store.cancel_appointment(appointment_id)
        return {
            "success": True,
            "action_taken": "cancel_appointment",
            "details": f"Appointment {appointment_id} has been cancelled."
        }

    def tool_route_to_queue(self, queue: str, reason: str, patient_id: Optional[str] = None) -> Dict[str, Any]:
        """Routes a ticket to an internal clinic queue."""
        valid_queues = self.store.clinic_info.get("routing_queues", [])
        if queue not in valid_queues:
            return {"success": False, "error": f"Invalid queue '{queue}'. Allowed: {valid_queues}"}

        return {
            "success": True,
            "routed_to": queue,
            "reason": reason,
            "patient_id": patient_id
        }