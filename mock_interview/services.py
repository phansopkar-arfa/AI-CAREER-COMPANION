"""
services.py — Mock Interview LLM Integration Layer (Groq API)

Handles all AI/LLM interactions for the mock interview module:
- Interview question generation
- Answer evaluation with scoring
- Full interview performance analysis
"""

import json
import os
import urllib.request
from django.conf import settings


# ─── Groq API Caller ─────────────────────────────────────────────

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


def _call_groq(system_prompt, user_prompt, max_tokens=1024, temperature=0.7):
    """
    Call the Groq LLM API and return response text.
    Uses llama-3.1-8b-instant for low-latency interview responses.
    """
    api_key = _get_groq_key()
    if not api_key:
        raise Exception("GROQ_API_KEY is missing. Please check your .env file.")

    try:
        payload = json.dumps({
            "model": "llama-3.1-8b-instant",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }).encode('utf-8')

        req = urllib.request.Request(
            'https://api.groq.com/openai/v1/chat/completions',
            data=payload,
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {api_key}',
                'User-Agent': 'Mozilla/5.0',
            }
        )

        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result['choices'][0]['message']['content'].strip()
    except Exception as e:
        print(f"Groq API Error: {str(e)}")
        raise Exception(f"AI Service Error: {str(e)}")


# ─── Prompt Templates ────────────────────────────────────────────

INTERVIEWER_SYSTEM_PROMPT = """You are an expert technical interviewer conducting a professional mock interview.
You are sharp, professional, and encouraging. Your questions are domain-specific and tailored to the candidate's resume.
Keep your responses focused, concise, and professional. Ask ONE question at a time.
Do NOT include any meta-commentary — just the question itself."""

EVALUATOR_SYSTEM_PROMPT = """You are an expert technical interview evaluator. Your goal is precision and strictness.
Evaluate the candidate's answer based on technical correctness, completeness, and clarity.
- For technical questions (e.g. "What is...", "Explain..."), answers like "yes", "no", "i don't know", or "okay" MUST receive a score of 0.
- ONLY for simple confirmation questions (e.g. "Are you ready?", "Do you understand the task?") can "yes" or "no" be acceptable (score 8-10).
- For partially correct but vague technical answers, give 2-4.
- For accurate and well-explained technical answers, give 8-10.
Be critical. Provide constructive feedback only for valid technical attempts.
Output ONLY valid JSON — no markdown fencing, no extra text."""

ANALYZER_SYSTEM_PROMPT = """You are a senior, highly critical technical interview panel lead. Provide a rigorous, data-driven analysis.
CRITICAL RULES for accuracy:
1. You MUST use the EXACT "Overall Performance Percentage" provided in the SCORING DATA. NEVER invent a score.
2. If the SCORING DATA shows low scores (0-4), your analysis MUST be professional but critical. Do NOT soften the blow with praise for non-existent strengths.
3. If the candidate failed to answer complex questions technically, you MUST flag this as a major failure in proficiency.
4. If there is only one response and it is poor, the fit for other domains must also be very low.
5. Absolute consistency between scores and text is mandatory.
Format your response in clean, readable sections with emoji indicators."""


def validate_answer_content(answer):
    """
    Validates user's spoken or typed answer to filter out noise,
    empty strings, or irrelevant single-word inputs before calling LLM.
    Returns: {"valid": bool, "reason": str}
    """
    clean_ans = answer.strip()
    if not clean_ans:
        return {"valid": False, "reason": "No answer provided."}
    
    # Only reject single characters or non-text noise. 
    # Words like "yes" or "no" are sent to the AI for contextual scoring.
    noise = {".", ",", "um", "uh", "hmm", "ah", "like", "so", "yeah"}
    if clean_ans.lower() in noise or len(clean_ans) < 2:
        return {"valid": False, "reason": "Answer is too short or lacks content."}
        
    return {"valid": True, "reason": ""}



# ─── Service Functions ───────────────────────────────────────────

def generate_first_question(domain, resume_text):
    """Generate the first interview question based on resume and domain."""
    prompt = f"""Based on the following resume and the target domain, generate an appropriate
first technical interview question. The question should be relevant to the candidate's
experience while testing their knowledge of {domain}.

Resume:
{resume_text}

Domain: {domain}

Generate ONLY the interview question — no preamble, no numbering, just the question."""

    return _call_groq(INTERVIEWER_SYSTEM_PROMPT, prompt, max_tokens=300, temperature=0.7)


def generate_next_question(domain, resume_text, messages):
    """Generate the next interview question based on conversation history."""
    conversation = "\n".join([
        f"{'Interviewer' if msg.get('role') == 'assistant' else 'Candidate'}: {msg.get('content', '')}"
        for msg in messages
    ])

    prompt = f"""Continue the technical interview for a {domain} position.
Based on the conversation so far, ask a relevant follow-up question that either:
- Digs deeper into the candidate's last answer
- Moves to a new topic from their resume
- Tests a different aspect of {domain}

Resume: {resume_text}

Conversation so far:
{conversation}

Generate ONLY the next interview question — no preamble, just the question."""

    return _call_groq(INTERVIEWER_SYSTEM_PROMPT, prompt, max_tokens=300, temperature=0.7)


def evaluate_answer(domain, question, answer, resume_text):
    """Evaluate a candidate's answer and return structured feedback."""
    prompt = f"""Evaluate this interview answer for a {domain} position.

Question: {question}
Candidate's Answer: {answer}

Resume context: {resume_text[:500]}

Respond in EXACT JSON format (no markdown, no extra text):
{{
    "score": <number 1-10>,
    "feedback": "<2-3 sentences of specific, constructive feedback>",
    "strengths": ["<strength 1>", "<strength 2>"],
    "improvements": ["<improvement 1>", "<improvement 2>"]
}}"""

    try:
        result_text = _call_groq(EVALUATOR_SYSTEM_PROMPT, prompt, max_tokens=400, temperature=0.3)
        if not result_text:
            return {"score": 5, "feedback": "Could not evaluate.", "strengths": [], "improvements": []}

        # Clean JSON response
        result_text = result_text.strip()
        if result_text.startswith('```'):
            result_text = result_text.split('\n', 1)[1].rsplit('```', 1)[0]

        return json.loads(result_text)
    except (json.JSONDecodeError, Exception):
        return {
            "score": 5,
            "feedback": "Answer received. Please continue with the next question.",
            "strengths": [],
            "improvements": []
        }


def analyze_interview_performance(domain, messages, proctoring_data=None, scoring_data=None):
    """
    Generate a comprehensive interview performance analysis.
    Includes proctoring data and actual per-question scores when available.
    """
    conversation = "\n".join([
        f"{'Interviewer' if msg.get('role') == 'assistant' else 'Candidate'}: {msg.get('content', '')}"
        for msg in messages if msg.get('role') != 'system'
    ])

    # Build actual scoring context from database
    scoring_section = """
    CRITICAL SCORING DATA:
    - Overall Performance Percentage: 0%
    - Evidence: No valid technical or detailed answers were provided during this session.
    - Evaluation: Technical proficiency is non-existent as no technical data was shared.
    """
    if scoring_data:
        avg_score = scoring_data.get('average_score', 0)
        total_questions = scoring_data.get('total_questions', 0)
        per_question = scoring_data.get('per_question_scores', [])

        if total_questions > 0:
            scoring_section = f"""
    ACTUAL SCORING DATA (YOU MUST USE THESE EXACT SCORES — do NOT invent your own):
    - Total Questions Answered: {total_questions}
    - Average Score: {avg_score}/10
    - Overall Performance Percentage: {round(avg_score * 10, 1)}%
    """
            if per_question:
                scoring_section += "    - Per-Question Breakdown:\n"
                for q in per_question:
                    scoring_section += f"      Q{q['number']}: {q['score']}/10 — {q['feedback']}\n"

            scoring_section += f"""
    CRITICAL: The Overall Performance score MUST be {round(avg_score * 10, 1)}% (derived from {avg_score}/10 average).
    Do NOT generate a random score. Use the actual data above."""

    # Build proctoring context section
    proctoring_section = ""
    if proctoring_data:
        tab_switches = proctoring_data.get('tab_switches', 0)
        face_violations = proctoring_data.get('face_violations', 0)
        time_used = proctoring_data.get('time_used', 0)
        total_duration = proctoring_data.get('total_duration', 1800)
        time_mins = round(time_used / 60, 1)
        total_mins = round(total_duration / 60, 1)

        integrity_items = []
        if tab_switches == 0 and face_violations == 0:
            integrity_items.append("Clean — no violations")
        if tab_switches > 0:
            integrity_items.append(f"⚠ {tab_switches} tab-switch violation(s)")
        if face_violations > 0:
            integrity_items.append(f"⚠ {face_violations} multi-face detection violation(s)")

        proctoring_section = f"""

    PROCTORING DATA (include in your analysis):
    - Tab Switches Detected: {tab_switches}
    - Multi-Face Violations: {face_violations}
    - Time Used: {time_mins} minutes out of {total_mins} minutes
    - Session Integrity: {'; '.join(integrity_items)}

    Include an "Interview Integrity" section in your analysis that evaluates the candidate's
    focus and discipline based on this proctoring data."""

    prompt = f"""As an expert technical interviewer, analyze the following interview conversation for a {domain} position.
    {scoring_section}

    Provide a detailed evaluation including:
    1. Overall Performance (EXACTLY as specified in the scoring section below — no deviations)
    2. Key Strengths (ONLY if evidenced by actual high-scoring answers. Write "None identified" if scores are low.)
    3. Areas for Improvement (Primary focus if scores are low)
    4. Communication Skills
    5. Technical Proficiency
    6. Specific Recommendations for Growth
    7. Interview Integrity (based on proctoring data)

    Then, based on the candidate's responses and demonstrated skills, analyze their potential fit for other technical domains.
    Consider their:
    - Technical knowledge breadth
    - Problem-solving approach
    - Learning ability
    - Communication style
    - Transferable skills

    For each potential alternative domain, provide:
    - Domain name
    - Fit percentage (CRITICAL: This MUST be strictly proportional to their actual interview accuracy. If overall accuracy is < 30%, these fits MUST be very low (< 10%).)
    - Key reasons for the fit
    - Required upskilling areas

    Interview Conversation:
    {conversation}
    {proctoring_section}

    Format the response in a clear, structured manner with emoji indicators for each section.
    Use the following format for domain suggestions:

    🔄 Domain Suitability Analysis:
    [Domain 1]
    - Fit: XX%
    - Strengths: [list]
    - Areas to Develop: [list]

    [Domain 2]
    - Fit: XX%
    - Strengths: [list]
    - Areas to Develop: [list]"""

    return _call_groq(ANALYZER_SYSTEM_PROMPT, prompt, max_tokens=2048, temperature=0.3)


