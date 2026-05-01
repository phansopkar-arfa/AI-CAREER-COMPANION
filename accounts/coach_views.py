"""
coach_views.py — API views for the AI Career Coach chatbot.

Uses Server-Sent Events (SSE) for real-time streaming responses
from the Groq LLM, avoiding the complexity of Django Channels.
"""

import os
import json
import urllib.request
import urllib.error

from django.http import JsonResponse, StreamingHttpResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.conf import settings

from .models import ChatMessage
from .services import UserContextService
from .prompts import build_system_prompt


def _get_groq_key():
    """Get Groq API key from env or .env file."""
    key = os.environ.get('GROQ_API_KEY', '')
    if not key:
        env_path = os.path.join(settings.BASE_DIR, '.env')
        if os.path.exists(env_path):
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith('GROQ_API_KEY='):
                        key = line.split('=', 1)[1].strip()
                        break
    return key


def _stream_groq_response(messages):
    """
    Call Groq API with streaming enabled.
    Yields chunks of text as they arrive.
    """
    api_key = _get_groq_key()
    if not api_key:
        yield "I'm sorry, the AI service is not configured. Please contact the administrator."
        return

    payload = json.dumps({
        "model": "llama-3.1-8b-instant",
        "messages": messages,
        "max_tokens": 1024,
        "temperature": 0.7,
        "stream": True,
    }).encode('utf-8')

    req = urllib.request.Request(
        'https://api.groq.com/openai/v1/chat/completions',
        data=payload,
        headers={
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + api_key,
            'User-Agent': 'Mozilla/5.0',
        }
    )

    try:
        resp = urllib.request.urlopen(req)
        buffer = b''
        while True:
            chunk = resp.read(256)
            if not chunk:
                break
            buffer += chunk
            # Process complete SSE lines
            while b'\n' in buffer:
                line, buffer = buffer.split(b'\n', 1)
                line = line.decode('utf-8').strip()
                if not line or not line.startswith('data: '):
                    continue
                data_str = line[6:]  # Remove 'data: ' prefix
                if data_str == '[DONE]':
                    return
                try:
                    data = json.loads(data_str)
                    delta = data.get('choices', [{}])[0].get('delta', {})
                    content = delta.get('content', '')
                    if content:
                        yield content
                except (json.JSONDecodeError, IndexError, KeyError):
                    continue
        resp.close()
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8', errors='replace')
        print(f"Groq API Error {e.code}: {error_body}")
        yield "I encountered an issue connecting to the AI service. Please try again."
    except Exception as e:
        print(f"Groq stream error: {e}")
        yield "Something went wrong. Please try again in a moment."


@csrf_exempt
@login_required
def coach_chat(request):
    """
    Main chat endpoint. Accepts POST with JSON body:
    { "message": "user text", "mode": "chat"|"warmup" }

    Returns SSE stream of AI response chunks.
    """
    if request.method != 'POST':
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    user_message = body.get('message', '').strip()
    mode = body.get('mode', 'chat')

    if not user_message:
        return JsonResponse({"error": "Empty message"}, status=400)

    # Save user message to history
    ChatMessage.objects.create(
        user=request.user,
        role='user',
        content=user_message
    )

    # Build context
    ctx_service = UserContextService(request.user)
    context_profile = ctx_service.build_context_profile()
    system_prompt = build_system_prompt(context_profile, mode=mode)

    # Build messages array with history
    chat_history = ctx_service.get_chat_history(limit=10)
    messages = [{"role": "system", "content": system_prompt}]

    # Add recent history (excluding the just-saved message, it's the last in history)
    for msg in chat_history[:-1]:  # Last one is the current message
        messages.append({"role": msg["role"], "content": msg["content"]})

    # Add current user message
    messages.append({"role": "user", "content": user_message})

    # Stream response via SSE
    def event_stream():
        full_response = []
        for chunk in _stream_groq_response(messages):
            full_response.append(chunk)
            # SSE format: each data line followed by double newline
            yield "data: " + json.dumps({"chunk": chunk}) + "\n\n"

        # Save complete assistant response
        complete_text = ''.join(full_response)
        if complete_text:
            ChatMessage.objects.create(
                user=request.user,
                role='assistant',
                content=complete_text
            )

        # Send completion signal
        yield "data: " + json.dumps({"done": True}) + "\n\n"

    response = StreamingHttpResponse(
        event_stream(),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


@csrf_exempt
@login_required
def coach_quick_action(request):
    """
    Handle quick action requests from the chat widget.
    Returns a pre-formatted message to feed into the chat.
    """
    if request.method != 'POST':
        return JsonResponse({"error": "POST required"}, status=405)

    body = json.loads(request.body)
    action = body.get('action', '')

    action_prompts = {
        "analyze_gaps": "Analyze my career gaps and give me a detailed action plan based on my test scores, resume, and overall profile.",
        "resume_tips": "Review my current resume data and give me 5 specific, actionable tips to improve it for ATS systems.",
        "interview_prep": "Based on my skills and experience, what are the top 5 interview questions I should prepare for? Give me sample answers.",
        "study_plan": "Create a 2-week study plan for me based on my weak subjects and upcoming placements.",
        "warmup": "I want to do a quick behavioral interview warm-up. Let's start!",
    }

    prompt = action_prompts.get(action, "Tell me how you can help me with my career preparation.")
    return JsonResponse({"prompt": prompt})


@csrf_exempt
@login_required
def coach_clear_history(request):
    """Clear chat history for the current user."""
    if request.method != 'POST':
        return JsonResponse({"error": "POST required"}, status=405)

    ChatMessage.objects.filter(user=request.user).delete()
    return JsonResponse({"status": "cleared"})


@login_required
def coach_history(request):
    """Return recent chat history as JSON."""
    messages = ChatMessage.objects.filter(
        user=request.user
    ).order_by('-created_at')[:20]

    history = [
        {
            "role": m.role,
            "content": m.content,
            "time": m.created_at.strftime("%I:%M %p"),
        }
        for m in reversed(messages)
    ]
    return JsonResponse({"history": history})
