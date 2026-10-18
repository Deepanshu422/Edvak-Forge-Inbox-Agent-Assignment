from datetime import datetime, timedelta
from typing import List, Dict, Any
from .store import ClinicStore

def normalize_provider_id(provider_id: str) -> str:
    """Normalizes provider names like 'Dr. James Okafor' to 'OKAFOR'."""
    p = (provider_id or "").upper()
    if "OKAFOR" in p:
        return "OKAFOR"
    if "PATEL" in p:
        return "PATEL"
    if "KIM" in p:
        return "KIM"
    return p.strip()

def normalize_visit_type(visit_type: str) -> str:
    """Normalizes visit type strings to valid clinic.json keys."""
    v = (visit_type or "follow_up").lower().strip().replace(" ", "_").replace("-", "_")
    if "physical" in v:
        return "annual_physical"
    if "new" in v:
        return "new_patient"
    if "sick" in v or "urgent" in v:
        return "sick_visit"
    if "tele" in v or "virtual" in v:
        return "telehealth"
    return "follow_up"

def is_clinic_open(store: ClinicStore, date_str: str) -> bool:
    """Checks weekends and clinic-wide holidays."""

    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    if date_obj.weekday() >= 5: # 5 for sat, 6 for sunday
        return False

    if date_str in store.clinic_info["holidays"]:
        return False

    return True

def is_provider_on_leave(store: ClinicStore, provider_id: str, date_str: str) -> bool:
    """Checks if a specific provider is on leave on the given date."""

    provider_id = normalize_provider_id(provider_id)
    provider = next((p for p in store.clinic_info["providers"] if p["id"] == provider_id), None)    
    if not provider or "leave" not in provider:
        return False

    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    for leave_period in provider["leave"]:
        start_leave = datetime.strptime(leave_period[0], "%Y-%m-%d")
        end_leave = datetime.strptime(leave_period[1], "%Y-%m-%d")
        if start_leave <= date_obj <= end_leave:
            return True

    return False

def get_available_slots(store: ClinicStore, provider_id: str, date_str: str, visit_type: str) -> Dict[str, Any]:
    """Returns available start times for a given provider, date, and visit type."""

    if not is_clinic_open(store, date_str):
        return {
            "available": False, 
            "reason": f"Clinic is closed on {date_str} (weekend or clinic holiday).", 
            "required_action": "offer_alternatives",
            "slots": []
        }

    if is_provider_on_leave(store, provider_id, date_str):
        return {
            "available": False, 
            "reason": f"Provider {provider_id} is on leave on {date_str}.", 
            "required_action": "offer_alternatives",
            "forbidden_actions": ["book_appointment", "book_on_leave"],
            "slots": []
        }

    # generating possible 20-mins slots
    all_slots = []
    current_time = datetime.strptime("09:00", "%H:%M")
    end_time = datetime.strptime("17:00", "%H:%M")
    lunch_start = datetime.strptime("12:00", "%H:%M")
    lunch_end = datetime.strptime("13:00", "%H:%M")

    while current_time < end_time:
        if not (lunch_start <= current_time < lunch_end):
            all_slots.append(current_time.strftime("%H:%M"))

        current_time += timedelta(minutes=20)

    # removing already booked slots
    appointments = store.get_appointments_by_provider_and_date(provider_id, date_str)
    booked_times = set()

    for appt in appointments:
        start_obj = datetime.strptime(appt.start, "%H:%M")
        end_obj = datetime.strptime(appt.end, "%H:%M")
        curr = start_obj
        while curr < end_obj:
            booked_times.add(curr.strptime(appt.start, "%H:%M"))
            curr += timedelta(minutes=20)

    open_slots = [s for s in all_slots if s not in booked_times]

    # for 40 mins visit, need to check 2 continuous 20 mins slots
    duration_mins = store.clinic_info["visit_types"].get(visit_type, 20)
    if duration_mins == 40:
        valid_40_min_slots = []

        for i in range(len(open_slots) - 1):
            slot1 = datetime.strptime(open_slots[i], "%H:%M")
            slot2 = datetime.strptime(open_slots[i+1], "%H:%M")
            if slot2 - slot1 == timedelta(minutes=20):
                valid_40_min_slots.append(open_slots[i])

        open_slots = valid_40_min_slots

    if not open_slots:
        return {
            "available": False, 
            "reason": "No slots available on this date.", 
            "slots": []}

    return {
        "available": True, 
        "reason": "Slots found.", 
        "slots": open_slots
    }
            
    
        