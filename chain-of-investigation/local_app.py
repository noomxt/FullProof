"""Local AI UI/API checks without Hardhat; no fake institutional verification."""
from fastapi import FastAPI
from backend_bridge import register_ai_routes
from verification import DEMO_POLICY
app=FastAPI(title='FullProof AI local demo')
cases={'DEMO_001':{'is_closed':False,'steps':[{'step_id':s['step_id'],'step_name':s['step_name']} for s in DEMO_POLICY['steps']]}}
store=register_ai_routes(app,cases)
