from django.shortcuts import render, get_object_or_404
import json
from django.http import JsonResponse
import time

from support.agents import run_support_agent
from .models import Conversation, Message

from orders.models import Order



def chat(request, order_id):
    if request.method == 'POST':
        data = json.loads(request.body)
        user_message = data.get("message")

        if not user_message:
            return JsonResponse({"error": "Empty message"}, status=400)
        
        order = get_object_or_404(Order, id=order_id, user=request.user)

        conversation, created = Conversation.objects.get_or_create(user=request.user, order=order)

        Message.objects.create(conversation=conversation, role="user", content=user_message)

        # send user message and conversation to LLM
        reply = run_support_agent(user_message, conversation.id, order.id, request.user.id)
        # store the LLM reply
        Message.objects.create(conversation=conversation, role="assistant", content=reply)
        
        # time.sleep(5)
        return JsonResponse({"reply": reply})