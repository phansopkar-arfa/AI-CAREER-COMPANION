"""
views.py — Mock Interview Django Views

Provides:
- interview_page: Full-page template view (extends base.html)
- api_start_interview: POST endpoint to start interview, get first question, create DB session
- api_answer_question: POST endpoint to validate/submit answer, track score, get next question
- api_end_interview: POST endpoint to end interview & generate full analysis
- api_pause_interview: POST endpoint to pause/resume an interview session
- api_report_violation: POST endpoint for tab-switch proctoring
- api_history: GET endpoint for past interview list
- api_dashboard: GET endpoint for aggregate analytics
- api_pdf_report: GET endpoint for downloading interview PDF report
"""

import json
import time as _time
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, FileResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.utils import timezone

from . import services
from .models import InterviewSession, QuestionResponse, ProctoringViolation
from .pdf_generator import generate_interview_pdf

# Default interview duration in seconds (30 minutes)
INTERVIEW_DURATION = 1800
# Penalty per tab switch in seconds
TAB_SWITCH_PENALTY = 30
# Max tab switches before auto-termination
MAX_TAB_SWITCHES = 3


def interview_page(request):
    """Render the main mock interview page."""
    domains = [
        "Software Development",
        "Data Science",
        "DevOps",
        "Machine Learning",
        "Web Development",
        "Cloud Computing",
        "Cybersecurity",
    ]
    return render(request, 'mock_interview/mock_interview.html', {
        'domains': domains,
        'interview_duration': INTERVIEW_DURATION,
    })


@csrf_exempt
@require_POST
def api_start_interview(request):
    """Start a new mock interview session and create database record."""
    try:
        body = json.loads(request.body)
        domain = body.get('domain', '').strip()
        resume_text = body.get('resume_text', '').strip()

        if not domain:
            return JsonResponse({'status': 'error', 'message': 'Domain is required.'}, status=400)
        if not resume_text:
            return JsonResponse({'status': 'error', 'message': 'Resume text is required.'}, status=400)

        question = services.generate_first_question(domain, resume_text)

        if not question:
            return JsonResponse({'status': 'error', 'message': 'Could not generate question.'}, status=500)

        # Create Database Session
        session = InterviewSession.objects.create(
            user=request.user if request.user.is_authenticated else None,
            domain=domain,
            resume_summary=resume_text[:1000],  # store just the start for context
            status='active'
        )

        # Initialize session state for proctoring
        request.session['interview_session_id'] = session.id
        request.session['interview_active'] = True
        request.session['interview_start'] = _time.time()
        request.session['interview_tab_switches'] = 0
        request.session['interview_domain'] = domain

        return JsonResponse({
            'status': 'success',
            'session_id': session.id,
            'question': question,
            'message': {'role': 'assistant', 'content': question},
            'session_duration': INTERVIEW_DURATION,
            'max_tab_switches': MAX_TAB_SWITCHES,
            'tab_switch_penalty': TAB_SWITCH_PENALTY,
        })

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON.'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
@require_POST
def api_answer_question(request):
    """Submit / validate an answer and get evaluation + next question."""
    try:
        body = json.loads(request.body)
        domain = body.get('domain', '').strip()
        resume_text = body.get('resume_text', '').strip()
        messages = body.get('messages', [])
        answer = body.get('answer', '').strip()

        session_id = request.session.get('interview_session_id')
        session_obj = InterviewSession.objects.filter(id=session_id).first() if session_id else None

        if not domain or not answer:
            return JsonResponse({'status': 'error', 'message': 'Domain and answer are required.'}, status=400)

        # Pre-validation (reject noise/empty without LLM call)
        validation = services.validate_answer_content(answer)
        
        last_question = ''
        for msg in reversed(messages):
            if msg.get('role') == 'assistant':
                last_question = msg.get('content', '')
                break

        if not validation['valid']:
            # Early return for invalid answers — do not save to DB, do not advance session.
            # Ask the user to provide more detail for the SAME question.
            return JsonResponse({
                'status': 'success',
                'evaluation': {
                    "score": 0,
                    "feedback": validation['reason'],
                    "strengths": [],
                    "improvements": ["Please provide more professional and technical details."]
                },
                'next_question': f"I see. Could you please provide a more detailed and technical explanation for my previous question? (Your response was too brief).",
                'message': {'role': 'assistant', 'content': f"I see. Could you please provide a more detailed and technical explanation for my previous question? (Your response was too brief)."},
                'current_average_score': session_obj.total_score if session_obj else 0.0,
            })

        # Evaluate via LLM (only reach here if validation passes)
        evaluation = services.evaluate_answer(domain, last_question, answer, resume_text)

        # Save to database (only for valid technical answers)
        if session_obj:
            session_obj.total_questions += 1
            QuestionResponse.objects.create(
                session=session_obj,
                question_number=session_obj.total_questions,
                question_text=last_question,
                answer_text=answer,
                score=evaluation.get('score', 0),
                feedback=evaluation.get('feedback', ''),
                strengths_text=json.dumps(evaluation.get('strengths', [])),
                improvements_text=json.dumps(evaluation.get('improvements', []))
            )
            # Update running average score
            session_obj.total_score = session_obj.compute_average_score()
            session_obj.save()

        # Generate next question
        next_question = services.generate_next_question(domain, resume_text, messages)
        if not next_question:
            next_question = "Could not generate next question. You may end the interview."

        return JsonResponse({
            'status': 'success',
            'evaluation': evaluation,
            'next_question': next_question,
            'message': {'role': 'assistant', 'content': next_question},
            'current_average_score': session_obj.total_score if session_obj else 0.0,
        })

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON.'}, status=400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
@require_POST
def api_pause_interview(request):
    """Pause or resume the current interview session."""
    try:
        body = json.loads(request.body)
        action = body.get('action', 'pause') # 'pause' or 'resume'
        
        session_id = request.session.get('interview_session_id')
        if not session_id:
            return JsonResponse({'status': 'error', 'message': 'No active session.'}, status=400)
            
        session_obj = InterviewSession.objects.filter(id=session_id).first()
        if session_obj:
            if action == 'pause':
                session_obj.status = 'paused'
            else:
                session_obj.status = 'active'
            session_obj.save()
            
        return JsonResponse({'status': 'success', 'session_status': session_obj.status if session_obj else action})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
@require_POST
def api_end_interview(request):
    """End interview, save proctoring stats, and fetch AI analysis."""
    try:
        body = json.loads(request.body)
        domain = body.get('domain', '').strip()
        messages = body.get('messages', [])
        tab_switches = body.get('tab_switches', 0)
        time_remaining = body.get('time_remaining', 0)

        if not domain or not messages:
            return JsonResponse({'status': 'error', 'message': 'Domain and messages are required.'}, status=400)

        time_used = INTERVIEW_DURATION - max(0, time_remaining)
        proctoring_data = {
            'tab_switches': tab_switches or request.session.get('interview_tab_switches', 0),
            'time_remaining': time_remaining,
            'total_duration': INTERVIEW_DURATION,
            'time_used': time_used,
            'face_violations': 0,
        }

        # Build actual scoring data from the database
        scoring_data = None
        session_id = request.session.get('interview_session_id')
        if session_id:
            session_obj = InterviewSession.objects.filter(id=session_id).first()
            if session_obj:
                proctoring_data['face_violations'] = session_obj.face_violations
                responses = session_obj.responses.all().order_by('question_number')
                if responses.exists():
                    per_question_scores = [
                        {'number': r.question_number, 'score': r.score, 'feedback': r.feedback[:100]}
                        for r in responses
                    ]
                    avg_score = round(sum(r.score for r in responses) / responses.count(), 1)
                    scoring_data = {
                        'total_questions': responses.count(),
                        'average_score': avg_score,
                        'per_question_scores': per_question_scores,
                    }

        analysis = services.analyze_interview_performance(domain, messages, proctoring_data, scoring_data)

        if session_id:
            session_obj = InterviewSession.objects.filter(id=session_id).first()
            if session_obj:
                session_obj.status = 'completed' if tab_switches < MAX_TAB_SWITCHES else 'terminated'
                session_obj.tab_switches = proctoring_data['tab_switches']
                session_obj.time_used = time_used
                session_obj.analysis_text = analysis
                session_obj.completed_at = timezone.now()
                session_obj.save()

        # Clear session
        for key in ['interview_active', 'interview_start', 'interview_tab_switches', 'interview_domain', 'interview_session_id']:
            request.session.pop(key, None)

        if not analysis:
            return JsonResponse({'status': 'error', 'message': 'Could not generate analysis.'}, status=500)

        return JsonResponse({
            'status': 'success',
            'session_id': session_id,
            'analysis': analysis,
        })

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
@require_POST
def api_report_violation(request):
    """Report a tab-switch proctoring violation."""
    try:
        switches = request.session.get('interview_tab_switches', 0) + 1
        request.session['interview_tab_switches'] = switches
        
        session_id = request.session.get('interview_session_id')

        if switches >= MAX_TAB_SWITCHES:
            request.session['interview_active'] = False
            if session_id:
                session_obj = InterviewSession.objects.filter(id=session_id).first()
                if session_obj:
                    session_obj.status = 'terminated'
                    session_obj.save()
                    
            return JsonResponse({
                'status': 'success',
                'action': 'terminate',
                'switches': switches,
                'penalty': TAB_SWITCH_PENALTY,
                'message': f'Interview terminated. {switches} tab switches detected.',
            })
        else:
            return JsonResponse({
                'status': 'success',
                'action': 'warn',
                'switches': switches,
                'penalty': TAB_SWITCH_PENALTY,
                'message': f'Warning {switches}/{MAX_TAB_SWITCHES}: Tab switch detected. {TAB_SWITCH_PENALTY}s penalty applied.',
            })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
@require_POST
def api_face_violation(request):
    """Report a multi-face detection proctoring violation."""
    MAX_FACE_VIOLATIONS = 3
    try:
        body = json.loads(request.body)
        faces_detected = body.get('faces_detected', 2)

        session_id = request.session.get('interview_session_id')
        if not session_id:
            return JsonResponse({'status': 'error', 'message': 'No active session.'}, status=400)

        session_obj = InterviewSession.objects.filter(id=session_id).first()
        if not session_obj:
            return JsonResponse({'status': 'error', 'message': 'Session not found.'}, status=404)

        session_obj.face_violations += 1
        session_obj.save(update_fields=['face_violations'])

        # Log the individual violation
        ProctoringViolation.objects.create(
            session=session_obj,
            violation_type='multi_face',
            details=f'{faces_detected} faces detected',
        )

        violations = session_obj.face_violations

        if violations >= MAX_FACE_VIOLATIONS:
            session_obj.status = 'terminated'
            session_obj.save(update_fields=['status'])
            return JsonResponse({
                'status': 'success',
                'action': 'terminate',
                'violations': violations,
                'message': f'Interview terminated. {violations} multi-face violations detected.',
            })
        else:
            return JsonResponse({
                'status': 'success',
                'action': 'warn',
                'violations': violations,
                'message': f'Warning {violations}/{MAX_FACE_VIOLATIONS}: Multiple faces detected ({faces_detected} faces).',
            })

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON.'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@require_GET
def api_history(request):
    """Fetch history of past interview sessions for the current user."""
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'success', 'history': []})
    sessions = InterviewSession.objects.filter(user=request.user).order_by('-created_at')[:20]
    data = []
    for s in sessions:
        data.append({
            'id': s.id,
            'domain': s.domain,
            'score': s.total_score,
            'questions': s.total_questions,
            'date': s.created_at.strftime('%Y-%m-%d %H:%M'),
            'status': s.status,
            'duration_mins': round(s.time_used / 60, 1) if s.time_used else 0
        })
    return JsonResponse({'status': 'success', 'history': data})


@require_GET
def api_dashboard(request):
    """Fetch aggregate dashboard analytics for the current user."""
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'success', 'dashboard': {
            'total_interviews': 0, 'average_score': 0.0, 'highest_score': 0.0,
            'total_face_violations': 0, 'avg_duration_mins': 0, 'trend': [],
            'recent_scores': [], 'domain_breakdown': [],
            'score_distribution': {'low': 0, 'mid': 0, 'high': 0},
        }})
    sessions = InterviewSession.objects.filter(user=request.user).exclude(status='active')
    total_interviews = sessions.count()

    if total_interviews == 0:
        return JsonResponse({
            'status': 'success',
            'dashboard': {
                'total_interviews': 0,
                'average_score': 0.0,
                'highest_score': 0.0,
                'total_face_violations': 0,
                'avg_duration_mins': 0,
                'trend': [],
                'recent_scores': [],
                'domain_breakdown': [],
                'score_distribution': {'low': 0, 'mid': 0, 'high': 0},
            }
        })

    scores = [s.total_score for s in sessions]
    avg_score = round(sum(scores) / total_interviews, 1)
    highest_score = round(max(scores), 1)
    total_face_violations = sum(s.face_violations for s in sessions)
    durations = [s.time_used for s in sessions if s.time_used]
    avg_duration_mins = round(sum(durations) / len(durations) / 60, 1) if durations else 0

    # Score distribution buckets
    low = sum(1 for s in scores if s < 4)
    mid = sum(1 for s in scores if 4 <= s < 7)
    high = sum(1 for s in scores if s >= 7)

    # Progress trend (last 10 sessions, chronological)
    trend_sessions = sessions.order_by('created_at')[:10]
    trend = [{'date': s.created_at.strftime('%m-%d'), 'score': s.total_score} for s in trend_sessions]

    # Recent scores (last 5, newest first)
    recent = sessions.order_by('-created_at')[:5]
    recent_scores = [{'domain': s.domain, 'score': s.total_score, 'date': s.created_at.strftime('%b %d')} for s in recent]

    # Domain breakdown
    domain_counts = {}
    for s in sessions:
        domain_counts[s.domain] = domain_counts.get(s.domain, 0) + 1
    domain_breakdown = [{'domain': d, 'count': c} for d, c in sorted(domain_counts.items(), key=lambda x: -x[1])]

    return JsonResponse({
        'status': 'success',
        'dashboard': {
            'total_interviews': total_interviews,
            'average_score': avg_score,
            'highest_score': highest_score,
            'total_face_violations': total_face_violations,
            'avg_duration_mins': avg_duration_mins,
            'trend': trend,
            'recent_scores': recent_scores,
            'domain_breakdown': domain_breakdown,
            'score_distribution': {'low': low, 'mid': mid, 'high': high},
        }
    })

@require_GET
def api_pdf_report(request, session_id):
    """Generate and return a PDF report for a specific interview session."""
    session = get_object_or_404(InterviewSession, id=session_id)
    
    try:
        pdf_buffer = generate_interview_pdf(session)
        response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="interview_report_{session.id}.pdf"'
        return response
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Failed to generate PDF: {str(e)}'}, status=500)

