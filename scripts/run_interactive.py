import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.mcp_server.server import MapleMCPServer
from src.agent.orchestrator import ClinicAgent
from dotenv import load_dotenv
from groq import Groq
load_dotenv()



def main():

    api_key = os.getenv("GROQ_API_KEY")
    llm_model = os.getenv("MODEL")
    if not api_key:
        print("ERROR: GROQ_API_KEY not found in .env file!")
        sys.exit(1)
    

    print("=" * 60)
    print("Maplewood Clinic — Interactive Agent Runner (Live Testing)")
    print("=" * 60)

    llm_client = Groq(api_key=api_key)
    
    server = MapleMCPServer(data_dir="data")
    agent = ClinicAgent(llm_client=llm_client, mcp_server=server, model=llm_model)

    while True:
        print("\nEnter incoming message details (or type 'exit' to quit):")
        body = input("Message body: ").strip()
        if body.lower() == "exit":
            break
        from_name = input("Sender Name (default: 'Anonymous'): ").strip() or "Anonymous"
        from_contact = input("Sender Contact (phone or email): ").strip()
        channel = input("Channel (sms/portal/email, default 'sms'): ").strip() or "sms"

        msg = {
            "id": "LIVE_TEST",
            "channel": channel,
            "from_name": from_name,
            "from_contact": from_contact,
            "body": body
        }

        print("\nProcessing through agent...")
        result = agent.process_message(msg)
        print("\nResult:")
        print(json.dumps(result, indent=2))
        print("-" * 60)

if __name__ == "__main__":
    main()