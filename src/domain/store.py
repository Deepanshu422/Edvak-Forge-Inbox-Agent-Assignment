import json
from typing import Dict, List, Optional
from .schemas import Patient, Medication, Appointment

class ClinicStore:

    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.clinic_info = self._load_json("clinic.json")
        self.patients: Dict[str, Patient] = self._load_patients()
        self.medications: List[Medication] = self._load_medications()

        # Appointments are stored in a dictionary keyed by ID so we can update them easily
        self.appointments: Dict[str, Appointment] = self._load_appointments()


    def _load_json(self, filename: str) -> dict | list:
        with open(f"{self.data_dir}/{filename}", "r") as f:
            return json.load(f)

    def _load_patients(self) -> Dict[str, Patient]:
        raw = self._load_json("patients.json")
        return {p["id"]: Patient(**p) for p in raw}

    def _load_medications(self) -> List[Medication]:
        raw = self._load_json("medications.json")
        return [Medication(**m) for m in raw]

    def _load_appointments(self) -> Dict[str, Appointment]:
        raw = self._load_json("appointments.json")
        return {a["id"]: Appointment(**a) for a in raw}

    def get_patient_by_id(self, patient_id: str) -> Optional[Patient]:
        return self.patients.get(patient_id)

    def get_medications_for_patient(self, patient_id: str) -> List[Medication]:
        return [m for m in self.medications if m.patient_id == patient_id]


    def get_appointments_by_provider_and_date(self, provider: str, date: str) -> List[Appointment]:
        return [
            a for a in self.appointments.values()
            if a.provider == provider and a.date == date and a.status == "booked"
        ]

    def update_appointment(self, appt_id: str, new_date: str, new_start: str, new_end: str):
        if appt_id in self.appointments:
            self.appointments[appt_id].date = new_date
            self.appointments[appt_id].start = new_start
            self.appointments[appt_id].end = new_end


    def cancel_appointment(self, appt_id: str):
        if appt_id in self.appointments:
            self.appointments[appt_id].status = "cancelled"

    def add_appointment(self, new_appt: Appointment):
        self.appointments[new_appt.id] = new_appt

    
    

        

        
