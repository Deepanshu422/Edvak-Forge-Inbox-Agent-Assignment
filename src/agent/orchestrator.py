import os
import json
from .prompts import SYSTEM_PROMPT
from .guardrails import apply_guardrails
from src.mcp_server.server import MapleMCPServer
from dotenv import load_dotenv

load_dotenv()  # Load from .env file
LLM_MODEL = os.getenv("MODEL") 

class ClinicAgent:

    def __init__(self, llm_client, mcp_server: MapleMCPServer, model: str = LLM_MODEL):
        self.client = llm_client 
        self.mcp_server = mcp_server
        self.model = model


    def process_message(self, message_data: dict) -> dict:
        """Runs the tool-calling loop for a single patient message."""
        
        # Pre-verify sender identity deterministically so patient_id is never missed
        pre_verify = self.mcp_server.tool_verify_patient(
            name=message_data.get("from_name", ""),
            contact=message_data.get("from_contact"),
            stated_dob=message_data.get("stated_dob"),
            body=message_data.get("body", "")
        )
        
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user", 
                "content": (
                    f"Incoming Message:\n{json.dumps(message_data, indent=2)}\n\n"
                    f"Initial Identity Check Result (from tool_verify_patient):\n{json.dumps(pre_verify, indent=2)}\n\n"
                    f"Call any additional tools needed (e.g., tool_check_refill, tool_get_patient_appointments, "
                    f"tool_find_slots, tool_book_appointment, tool_reschedule_appointment, tool_cancel_appointment) "
                    f"and then return the final JSON."
                )
            }
        ]
        
        tools = self.get_tool_schemas()
        tool_names_called = ["tool_verify_patient"]

        # Multi-turn tool execution loop (max 5 turns)
        for _ in range(5):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                    temperature=0.0,
                )
            except Exception as e:

                # handling LLMs intermittent 'tool_use_failed' 
                err_str = str(e)
                if "tool_use_failed" in err_str or "failed_generation" in err_str:
                    fallback_resp = self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        temperature=0.0,
                        response_format={"type": "json_object"}
                    )
                    raw_output = json.loads(fallback_resp.choices[0].message.content)
                    raw_output["id"] = message_data.get("id", raw_output.get("id"))
                    raw_output["tool_calls"] = list(set(tool_names_called))
                    return apply_guardrails(raw_output)
                raise e
            
            choice = response.choices[0]
            message = choice.message

            # If the LLM requested tool calls
            if message.tool_calls:
                # Append assistant message with its tool calls to history
                messages.append(message)

                for tc in message.tool_calls:
                    fn_name = tc.function.name
                    tool_names_called.append(fn_name)
                    
                    try:
                        fn_args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                    except Exception:
                        fn_args = {}

                    # Execute the tool on our MCP server
                    result = self.execute_tool(fn_name, fn_args)

                    # Send tool execution result back to LLM
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": fn_name,
                        "content": json.dumps(result)
                    })
            else:

                content = (message.content or "").strip()
                # markdown code fences if present
                if content.startswith("```"):
                    content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
                # LLM finished calling tools and returned the final JSON
                try:
                    raw_output = json.loads(content)
                except Exception:
                    fallback_resp = self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        temperature=0.0,
                        response_format={"type": "json_object"}
                    )
                    raw_output = json.loads(fallback_resp.choices[0].message.content)

                raw_output["id"] = message_data.get("id", raw_output.get("id"))
                raw_output["tool_calls"] = list(set(tool_names_called))

                # Pass through strict safety and privacy guardrails
                return apply_guardrails(raw_output)

        return {
            "id": message_data.get("id"),
            "patient_id": None,
            "intents": ["other"],
            "urgency": "routine",
            "actions": ["route_to_front_desk"],
            "routed_to": ["front_desk"],
            "tool_calls": list(set(tool_names_called)),
            "reply_draft": "We received your message and our front desk will review it shortly."
        }
        
    def execute_tool(self, name: str, args: dict) -> dict:
        """Routes LLM tool calls to the underlying MCP server methods."""
        if name == "tool_verify_patient":
            return self.mcp_server.tool_verify_patient(**args)
        elif name == "tool_get_patient_appointments":
            return self.mcp_server.tool_get_patient_appointments(**args)
        elif name == "tool_check_refill":
            return self.mcp_server.tool_check_refill(**args)
        elif name == "tool_find_slots":
            return self.mcp_server.tool_find_slots(**args)
        elif name == "tool_book_appointment":
            return self.mcp_server.tool_book_appointment(**args)
        elif name == "tool_reschedule_appointment":
            return self.mcp_server.tool_reschedule_appointment(**args)
        elif name == "tool_cancel_appointment":
            return self.mcp_server.tool_cancel_appointment(**args)
        elif name == "tool_route_to_queue":
            return self.mcp_server.tool_route_to_queue(**args)
        
        return {"error": f"Tool '{name}' not found."}   
         
    def get_tool_schemas(self) -> list:

        """Compact schemas for all 8 MCP tools."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "tool_verify_patient",
                    "description": "Verifies patient or caregiver identity against clinic records.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "contact": {"type": "string", "description": "Phone or email"},
                            "stated_dob": {"type": "string", "description": "YYYY-MM-DD"}
                        },
                        "required": ["name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "tool_get_patient_appointments",
                    "description": "Lists existing booked appointments for a verified patient.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "patient_id": {"type": "string"}
                        },
                        "required": ["patient_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "tool_check_refill",
                    "description": "Checks 5-gate refill eligibility for a medication.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "patient_id": {"type": "string"},
                            "medication_name": {"type": "string"}
                        },
                        "required": ["patient_id", "medication_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "tool_find_slots",
                    "description": "Finds open appointment slots for a provider, date, and visit type.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "provider_id": {"type": "string"},
                            "date_str": {"type": "string", "description": "YYYY-MM-DD"},
                            "visit_type": {"type": "string"}
                        },
                        "required": ["provider_id", "date_str", "visit_type"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "tool_book_appointment",
                    "description": "Books a new appointment in the clinic calendar.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "patient_id": {"type": "string"},
                            "provider_id": {"type": "string"},
                            "date_str": {"type": "string", "description": "YYYY-MM-DD"},
                            "start_time": {"type": "string", "description": "HH:MM"},
                            "visit_type": {"type": "string"}
                        },
                        "required": ["patient_id", "provider_id", "date_str", "start_time", "visit_type"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "tool_reschedule_appointment",
                    "description": "Reschedules an existing appointment to a new date and time.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "appointment_id": {"type": "string"},
                            "new_date": {"type": "string", "description": "YYYY-MM-DD"},
                            "new_start": {"type": "string", "description": "HH:MM"},
                            "provider_id": {"type": "string"}
                        },
                        "required": ["appointment_id", "new_date", "new_start"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "tool_cancel_appointment",
                    "description": "Cancels an existing appointment.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "appointment_id": {"type": "string"}
                        },
                        "required": ["appointment_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "tool_route_to_queue",
                    "description": "Routes message to clinician_urgent, clinician_routine, provider_refills, front_desk, or billing.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "queue": {"type": "string"},
                            "reason": {"type": "string"},
                            "patient_id": {"type": "string"}
                        },
                        "required": ["queue", "reason"]
                    }
                }
            }
        ]

