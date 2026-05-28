from anthropic import Anthropic
from django.conf import settings
from .tools import get_order_details, get_refund_history, check_delivery_status
from .models import Conversation, Message, AgentLog


# Initialize Anthropic client
client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)

anthropic_model = settings.ANTHROPIC_MODEL


# SUPPORT SYSTEM PROMPT --> Maya's job description
SUPPORT_SYSTEM_PROMPT = """
You are Maya, a customer support agent at CoolBreeze AC.
You help customers with issues related to their AC orders.

Your responsibilities:
- Always use your tools to gather facts before responding
- Check order details when customer mentions their order
- Check refund history before making any refund decisions
- Be empathetic but honest

Your personality:
- Friendly and professional
- Patient even when customer is angry
- Clear and concise in your replies
- No emojies

Important rules:
- Always check order details first before responding
- Never approve or deny a refund yourself
- If refund decision is needed — tell customer you are checking with your team
"""


MANAGER_SYSTEM_PROMPT = """
You are a senior support manager at CoolBreeze AC.
A support agent has escalated a customer case to you for a refund decision.

Your responsibilities:
- Review the case summary carefully
- Consider the customer's refund history
- Make a fair and final refund decision
- Give a clear reason for your decision

Your decision options:
- Approve refund — if the case is genuine and within policy
- Deny refund — if the case is suspicious or outside policy
- Escalate to risk team — if you suspect fraud

Important rules:
- Be fair but firm
- Base decision on facts — not emotions
- Always give a specific reason for your decision
- Keep your response concise and professional
"""

# SUPPORT TOOLS --> Tool schemas, that ai agents will read
SUPPORT_TOOLS = [
    {
        "name": "get_order_details",
        "description": "Fetch complete order details including status, carrier, tracking number and days since order was placed. Use this when customer mentions their order or complains about delivery.",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "integer",
                    "description": "The order ID to look up"
                }
            },
            "required": ["order_id"]
        }
    },

    {
        "name": "get_refund_history",
        "description": "Get complete refund history for a user. Use this before making any refund related decisions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "The user ID to check refund history for"
                }
            },
            "required": ["user_id"]
        }
    },

    {
        "name": "check_delivery_status",
        "description": "Check current delivery status using tracking number and carrier. Use this when customer complains about delayed or missing delivery.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tracking_number": {
                    "type": "string",
                    "description": "The shipment tracking number"
                },
                "carrier": {
                    "type": "string",
                    "description": "The carrier name for example BlueDart or Delhivery"
                }
            },
            "required": ["tracking_number", "carrier"]
        }
    },

    {
        "name": "escalate_to_manager",
        "description": "Escalate the case to the manager for a refund decision. Use this when customer requests a refund or compensation. Prepare a detailed case summary including order details, refund history and customer complaint before escalating.",
        "input_schema": {
            "type": "object",
            "properties": {
                "case_summary": {
                    "type": "string",
                    "description": "Complete case summary including order details, refund history and customer complaint"
                }
            },
            "required": ["case_summary"]
        }
    }


]


# execute_tool() --> bridge between claude and python functions (tools)
def execute_tool(tool_name, tool_input):
    if tool_name == "get_order_details":
        return get_order_details(tool_input["order_id"])
    
    if tool_name == "get_refund_history":
        return get_refund_history(tool_input["user_id"])
    
    if tool_name == "check_delivery_status":
        return check_delivery_status(tool_input["tracking_number"], tool_input["carrier"])
    
    if tool_name == "escalate_to_manager":
        case_summary = tool_input["case_summary"]
        print("escalating to manager=====>", case_summary)
        decision = run_manager_agent(case_summary)
        print("decision===>", decision)
        return decision


# Agent Loop --> while loop that loops until the task is done
def run_support_agent(user_message, conversation_id, order_id, user_id):
    conv = Conversation.objects.get(id=conversation_id)

    conversation_messages = []
    for msg in conv.messages.order_by("created_at"):
        conversation_messages.append({
            "role": msg.role,
            "content": msg.content
        })

    while True:
        # send this conversation to LLM
        response = client.messages.create(
            model=anthropic_model,
            max_tokens=1024,
            system=SUPPORT_SYSTEM_PROMPT + f"\n\nContext: This conversation is about Order #{order_id}, user: {user_id}",
            tools=SUPPORT_TOOLS,
            messages=conversation_messages
        )

        if response.stop_reason == 'tool_use':
            tool_result = []
            for block in response.content:
                if block.type == 'tool_use':
                    # execute the tool
                    result = execute_tool(block.name, block.input)

                    tool_result.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(result)
                    })
            
            conversation_messages.append({
                "role": "assistant",
                "content": response.content
            })

            conversation_messages.append({
                "role": "user",
                "content": tool_result
            })

        else:
            return response.content[0].text
        

def run_manager_agent(case_summary):
    manager_messages = [
        {"role": "user", "content": case_summary} # user is task giver
    ]

    while True:
        response = client.messages.create(
            model=anthropic_model,
            max_tokens=1024,
            system=MANAGER_SYSTEM_PROMPT,
            messages=manager_messages
        )

        if response.stop_reason == 'tool_use':
            tool_result = []
            for block in response.content:
                if block.type == 'tool_use':
                    result = execute_tool(block.name, block.input)

                    tool_result.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(result)
                    })
            manager_messages.append({
                "role": "assistant",
                "content": response.content
            })

            manager_messages.append({
                "role": "user",
                "content": tool_result
            })
        else:
            return response.content[0].text


