import json
import os
import sys
from dotenv import load_dotenv
from groq import Groq
import time

# Load environment variables
load_dotenv()

# root directory is on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.mcp_server.server import MapleMCPServer
from src.agent.orchestrator import ClinicAgent
from src.eval.metrics import evaluate_predictions
from src.eval.reporter import generate_markdown_report  


def main():

    api_key = os.getenv("GROQ_API_KEY")
    llm_model = os.getenv("MODEL")
    if not api_key:
        print("ERROR: GROQ_API_KEY not found in .env file!")
        sys.exit(1)


    print("=" * 60)
    print("Maplewood Clinic Front-Desk Agent — Benchmark Runner")
    print("=" * 60)

    llm_client = Groq(api_key=api_key)

    # Load files
    with open("data/messages_sample.json", "r") as f:
        messages = json.load(f)
    with open("data/labels_sample.json", "r") as f:
        labels = json.load(f)

    # initializing server and agent
    mcp_server = MapleMCPServer(data_dir="data")
    agent = ClinicAgent(llm_client=llm_client, mcp_server=mcp_server, model=llm_model)

    # Resume Logic: Load existing predictions if present to prevent re-processing and hitting rate limits
    predictions = []
    processed_ids = set()
    predictions_path = "outputs/predictions.json"
    
    if os.path.exists(predictions_path):
        try:
            with open(predictions_path, "r", encoding="utf-8") as f:
                predictions = json.load(f)
                processed_ids = {p["id"] for p in predictions if "id" in p}
            print(f"\nResuming from checkpoint: Found {len(processed_ids)} already processed messages in outputs/predictions.json")
        except Exception:
            predictions = []
            processed_ids = set()

    print(f"\nProcessing {len(messages)} incoming inbox messages...")

    for i, msg in enumerate(messages, 1):
        msg_id = msg['id']
        if msg_id in processed_ids:
            print(f"[{i:02d}/40] Skipping {msg_id} (Already processed in checkpoint).")
            continue

        print(f"[{i:02d}/40] Processing {msg_id} ({msg['channel']}) from {msg['from_name']}...")
        result = agent.process_message(msg)
        predictions.append(result)
        
        # Save incrementally so progress is never lost
        os.makedirs("outputs", exist_ok=True)
        with open(predictions_path, "w", encoding="utf-8") as f:
            json.dump(predictions, f, indent=2, ensure_ascii=False)
            
        time.sleep(0.5)

    # Saving predictions
    os.makedirs("outputs", exist_ok=True)
    with open(predictions_path, "w", encoding="utf-8") as f:
        json.dump(predictions, f, indent=2, ensure_ascii=False)
    print("\nSaved predictions to outputs/predictions.json")

    # Evaluate and save Markdown report
    metrics = evaluate_predictions(predictions, labels)
    report_md = generate_markdown_report(metrics)
    with open("outputs/evaluation_report.md", "w") as f:
        f.write(report_md)
    print("Saved evaluation report to outputs/evaluation_report.md")

    # Printing detailed summary to terminal
    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)
    print(f"Total Messages Processed: {metrics['total_messages']}")
    print(f"Emergency Recall:         {metrics['emergency_recall']:.1f}%")
    print(f"must_not Violations:      {metrics['total_must_not_violations']}")
    print(f"Urgency Accuracy:         {metrics['urgency_accuracy']:.1f}%")
    print(f"Action Set Match:         {metrics['action_accuracy']:.1f}%")

    if metrics["must_not_violations"]:
        print("\nVIOLATIONS FOUND:")
        for v in metrics["must_not_violations"]:
            print(f"  - Message {v['id']}: Forbidden '{v['forbidden_action']}' triggered!")
            print(f"    Predicted Actions: {v['predicted_actions']}")
            print(f"    Trap: {v['trap_note']}")
    else:
        print("\nZERO must_not violations detected. 100% Policy Compliant.")

    if metrics["missed_emergencies"]:
        print("\nMISSED EMERGENCIES:")
        for e in metrics["missed_emergencies"]:
            print(f"  - Message {e['id']}: Predicted {e['predicted_urgency']}, Expected {e['expected_urgency']}")
    else:
        print("ZERO emergencies missed. 100% Emergency Recall.")

if __name__ == "__main__":
    main()