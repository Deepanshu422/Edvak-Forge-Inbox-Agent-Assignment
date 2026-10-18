# src/agent/guardrails.py

def apply_guardrails(agent_output: dict) -> dict:
    """Enforces absolute clinic policies and cleans action/intent sets on the LLM's output."""

    actions = set(agent_output.get("actions", []))
    intents = set(agent_output.get("intents", []))
    current_routes = set(agent_output.get("routed_to", []))
    urgency = str(agent_output.get("urgency", "routine")).lower()

    # for emergency
    if urgency == "emergency" or "escalate_emergency" in actions:
        urgency = "emergency"
        actions = {"escalate_emergency"}  # Never allow prepare_refill_for_approval or advice in an emergency
        current_routes.add("clinician_urgent")
        intents.add("clinical")
        intents.discard("emergency")
        
        agent_output["reply_draft"] = (
            "This sounds like a medical emergency. Please call 911 or go to the nearest "
            "emergency department immediately. We have alerted our clinical team."
        )

    # privacy
    if "request_verification" in actions or "decline_disclosure" in actions:
        agent_output["reply_draft"] = (
            "For your privacy, we cannot disclose health information or appointment details. "
            "Please verify your identity by calling the clinic or using the patient portal."
        )

    if "prepare_refill_for_approval" in actions and "refill_needs_visit" not in actions:
        actions.discard("route_to_provider")

    if "answer_directly" in actions and not intents.intersection({"admin", "new_patient"}):
        if len(actions) > 1:
            actions.discard("answer_directly")

    if "acknowledge" in actions and len(actions) > 1:
        actions.discard("acknowledge")

    if "offer_alternatives" in actions:
        actions.discard("offer_appointment")
        actions.discard("route_to_front_desk")
        current_routes.discard("front_desk")

    if "refill_too_early" in actions:
        actions.discard("offer_alternatives")
        actions.discard("offer_appointment")

    # strict vocabulary enforcement to prevent LLM hallucinations
    allowed_actions = {
        "escalate_emergency", "route_to_clinician", "route_to_provider", "route_to_billing", 
        "route_to_front_desk", "prepare_refill_for_approval", "refill_needs_visit", "refill_too_early", 
        "book_appointment", "reschedule_appointment", "cancel_appointment", "offer_appointment", 
        "offer_alternatives", "offer_new_patient_booking", "request_verification", "decline_disclosure", 
        "flag_suspicious_instruction", "answer_directly", "acknowledge", "no_action"
    }
    allowed_intents = {
        "refill", "reschedule", "clinical", "new_patient", "billing", "schedule", 
        "records", "cancel", "admin", "third_party", "other", "spam"
    }
    allowed_queues = {
        "clinician_urgent", "clinician_routine", "provider_refills", "front_desk", "billing"
    }
    allowed_urgencies = {"emergency", "urgent", "routine"}

    agent_output["actions"] = sorted(list(actions.intersection(allowed_actions)))
    agent_output["intents"] = sorted(list(intents.intersection(allowed_intents))) or ["other"]
    agent_output["routed_to"] = sorted(list(current_routes.intersection(allowed_queues)))
    agent_output["urgency"] = urgency if urgency in allowed_urgencies else "routine"
    
    return agent_output