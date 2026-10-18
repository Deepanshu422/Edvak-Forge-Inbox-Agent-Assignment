# app.py
import streamlit as st
import json
import os
from src.mcp_server.server import MapleMCPServer
from src.agent.orchestrator import ClinicAgent
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")
model = os.getenv("MODEL")

if not api_key:
    st.error("GROQ_API_KEY not found in .env file!")
    st.stop()

if not model:
    st.error("MODEL not found in .env file!")
    st.stop()

llm_client = Groq(api_key=api_key)

st.set_page_config(page_title="Maplewood Clinic AI Agent", layout="wide")
st.title("🏥 Maplewood Clinic — Front-Desk Agent Workbench")



@st.cache_resource
def get_system():
    server = MapleMCPServer(data_dir="data")
    agent = ClinicAgent(llm_client=llm_client, mcp_server=server, model=model)
    return server, agent

server, agent = get_system()

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("Incoming Message Input")
    sender_name = st.text_input("Sender Name", value="Aisha Johnson")
    contact = st.text_input("Sender Contact", value="555-0103")
    channel = st.selectbox("Channel", ["sms", "portal", "email"])
    body = st.text_area("Message Body", value="Woke up with crushing chest pain going into my left arm, feel sweaty and dizzy.")
    
    process_btn = st.button("Process Message", type="primary")

with col2:
    st.subheader("Agent Output & MCP State")
    if process_btn:
        msg = {
            "id": "DEMO_MSG",
            "channel": channel,
            "from_name": sender_name,
            "from_contact": contact,
            "body": body
        }
        with st.spinner("Processing through MCP tools & Agent Orchestrator..."):
            result = agent.process_message(msg)
            
        st.json(result)
        
        if result.get("urgency") == "emergency":
            st.error("🚨 Medical Emergency Escalation Triggered — Zero Automated Clinical Advice Allowed.")
        else:
            st.success("Message Processed within Clinical Governance Policies.")