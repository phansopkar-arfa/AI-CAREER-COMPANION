import os
import json
import random
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse

from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.utils import timezone
from .forms import CustomUserCreationForm, CustomAuthenticationForm
from django.template.loader import render_to_string
from .models import Question, Subject, TestResult, Resume

# Lazy imports for optional AI libraries
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

try:
    import google.generativeai as genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

try:
    import pandas as pd
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    HAS_ML = True
except ImportError:
    HAS_ML = False


UPLOAD_FOLDER = 'media/uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def _send_sms(number, message):
    """Real SMS delivery via Fast2SMS."""
    import urllib.request
    api_key = getattr(settings, 'FAST2SMS_API_KEY', '')
    if not api_key:
        print(f"[INTERNAL] FAST2SMS_API_KEY is missing. Code: {message}")
        return False
        
    url = f"https://www.fast2sms.com/dev/bulkV2?authorization={api_key}&route=otp&variables_values={message}&numbers={number}"
    
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            return res_data.get('return', False)
    except Exception as e:
        print(f"[SMS ERROR] Failed to send: {str(e)}")
        return False


# ============ AUTH VIEWS ============

def home(request):
    if not request.user.is_authenticated:
        return render(request, 'accounts/home.html')
    
    # Career Metrics
    latest_resume = Resume.objects.filter(user=request.user).first()
    results = TestResult.objects.filter(user=request.user).order_by('-date')
    
    avg_accuracy = 0
    if results.exists():
        avg_accuracy = round(sum(r.percentage for r in results) / results.count(), 1)
    
    # Recent Activity (Combined)
    recent_tests = results[:3]

    # Pre-process display name for templates
    display_name = request.user.name
    if not display_name:
        display_name = request.user.email.split('@')[0].capitalize()
    
    return render(request, 'accounts/home.html', {
        'resume': latest_resume,
        'avg_test_score': avg_accuracy,
        'recent_activity': recent_tests,
        'display_name': display_name,
    })

def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Registration successful. Please log in.")
            return redirect('login')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = CustomUserCreationForm()
    return render(request, 'accounts/register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('home')
        else:
            messages.error(request, "Invalid credentials.")
    else:
        form = CustomAuthenticationForm()
    return render(request, 'accounts/login.html', {'form': form})

def demo_view(request):
    return render(request, 'accounts/demo.html')

def logout_view(request):
    logout(request)
    return redirect('home')

def password_reset_request(request):
    """Initial step: Request password reset via Registration No & Phone + OTP Simulator."""
    if request.method == 'POST':
        reg_no = request.POST.get('registration', '').strip()
        phone = request.POST.get('phone', '').strip()
        
        from .models import UserProfile
        user = UserProfile.objects.filter(registration=reg_no, phone=phone).first()
        
        if user:
            # Generate 6-digit OTP
            otp = str(random.randint(100000, 999999))
            request.session['reset_otp'] = otp
            request.session['reset_user_id'] = user.id
            
            # TERMINAL SIMULATOR (Secure local delivery)
            print("\n" + "="*50)
            print(f"🔑 PASSWORD RESET REQUEST AUTHORIZED")
            print(f"📱 Target Phone: {user.phone}")
            print(f"🔒 SECURE OTP: {otp}")
            print("="*50 + "\n")
            
            messages.success(request, f"Registration verified. A secure code has been dispatched to terminal for verification.")
            return render(request, 'accounts/password_reset_otp.html')
        else:
            messages.error(request, "Identity verification failed. Registration or phone number is incorrect.")
            
    return render(request, 'accounts/password_reset_request.html')

def password_reset_confirm(request):
    """Verification step: Check OTP and set New Password."""
    if request.method == 'POST':
        user_id = request.session.get('reset_user_id')
        session_otp = request.session.get('reset_otp')
        input_otp = request.POST.get('otp', '').strip()
        
        new_password = request.POST.get('password1')
        confirm_password = request.POST.get('password2')
        
        # Verify OTP first
        if not session_otp or input_otp != session_otp:
            messages.error(request, "Invalid or expired OTP.")
            return render(request, 'accounts/password_reset_otp.html')

        if not new_password or new_password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, 'accounts/password_reset_otp.html')
            
        from .models import UserProfile
        user = UserProfile.objects.filter(id=user_id).first()
        if user:
            user.set_password(new_password)
            user.save()
            # Clean up
            request.session.pop('reset_otp', None)
            request.session.pop('reset_user_id', None)
            messages.success(request, "Credentials updated. Please sign in.")
            return redirect('login')
            
    return redirect('login')

def resend_otp(request):
    """Resend OTP to the user in session (SMS Simulator)."""
    user_id = request.session.get('reset_user_id')
    from .models import UserProfile
    user = UserProfile.objects.filter(id=user_id).first()
    
    if user:
        otp = str(random.randint(100000, 999999))
        request.session['reset_otp'] = otp
        
        # TERMINAL SIMULATOR
        print("\n" + "="*50)
        print(f"🔄 NEW OTP GENERATED (RESEND)")
        print(f"🔒 NEW SECURE OTP: {otp}")
        print("="*50 + "\n")
        
        messages.success(request, "A new verification code has been dispatched to your terminal.")
                
    return render(request, 'accounts/password_reset_otp.html')


# ============ ATS EVALUATOR ============

def ats_evaluator_redirect(request):
    return redirect("http://localhost:8502")




# ============ TEST & EVALUATION MODULE ============

@login_required
def career_test(request):
    technical = Subject.objects.filter(category='technical')
    company = Subject.objects.filter(category='company')
    aptitude = Subject.objects.filter(category='aptitude')
    return render(request, 'accounts/career_test.html', {
        'technical_subjects': technical,
        'company_subjects': company,
        'aptitude_subjects': aptitude,
    })

@login_required
def test_info(request, subject_slug):
    subject = get_object_or_404(Subject, slug=subject_slug)
    total_questions = Question.objects.filter(subject=subject).count()
    return render(request, 'accounts/test_info.html', {
        'subject': subject,
        'total_questions': total_questions,
        'test_questions': min(30, total_questions),
        'test_duration': 30,
    })

@login_required
def start_test(request, subject_slug):
    subject = get_object_or_404(Subject, slug=subject_slug)
    
    # Check if user is resuming an active test session for this subject
    import dateutil.parser
    from django.utils import timezone
    
    time_remaining_seconds = 1800 # 30 mins defaults
    
    if request.session.get('test_subject_id') == subject.id and 'test_question_ids' in request.session:
        start_time_str = request.session.get('test_start_time')
        if start_time_str:
            try:
                start_time = dateutil.parser.isoparse(start_time_str)
                delta = (timezone.now() - start_time).total_seconds()
                
                # If still within the 30-minute window
                if delta < 1800:
                    time_remaining_seconds = int(1800 - delta)
                    question_ids = request.session['test_question_ids']
                    # Retrieve the exact questions we saved
                    qs = list(Question.objects.filter(id__in=question_ids))
                    # Reorder them to match the original randomized order
                    questions = sorted(qs, key=lambda q: question_ids.index(q.id))
                    
                    return render(request, 'accounts/test_page.html', {
                        'questions': questions,
                        'subject': subject,
                        'time_remaining_seconds': time_remaining_seconds,
                    })
            except Exception as e:
                pass # Fallback to new session

    # New Session:
    questions = list(Question.objects.filter(subject=subject))
    random.shuffle(questions)
    questions = questions[:30]

    # Store question IDs in session for grading
    request.session['test_question_ids'] = [q.id for q in questions]
    request.session['test_subject_id'] = subject.id
    request.session['test_start_time'] = timezone.now().isoformat()

    return render(request, 'accounts/test_page.html', {
        'questions': questions,
        'subject': subject,
        'time_remaining_seconds': 1800,
    })

@login_required
def submit_test(request, subject_slug):
    if request.method != 'POST':
        return redirect('career_test')

    subject = get_object_or_404(Subject, slug=subject_slug)
    question_ids = request.session.get('test_question_ids', [])
    questions = Question.objects.filter(id__in=question_ids)

    score = 0
    total = len(questions)

    for question in questions:
        selected = request.POST.get(str(question.id))
        if selected and selected.upper() == question.correct_answer.upper():
            score += 1

    percentage = round((score / total) * 100, 2) if total > 0 else 0
    violations = int(request.POST.get('violations', 0))
    tab_switches = int(request.POST.get('tab_switches', 0))
    auto_submitted = request.POST.get('auto_submitted') == 'true'
    time_taken = int(request.POST.get('time_taken', 0))

    TestResult.objects.create(
        user=request.user,
        subject=subject,
        score=score,
        total_questions=total,
        percentage=percentage,
        time_taken=time_taken,
        violations=violations,
        tab_switches=tab_switches,
        auto_submitted=auto_submitted,
    )

    # Clean up session
    for key in ['test_question_ids', 'test_subject_id', 'test_start_time']:
        request.session.pop(key, None)

    return redirect('dashboard')

@login_required
def dashboard(request):
    results = TestResult.objects.filter(user=request.user).order_by('-date')
    total_tests = results.count()
    average_accuracy = 0
    best_score = 0

    if total_tests > 0:
        average_accuracy = round(sum(r.percentage for r in results) / total_tests, 1)
        best_score = round(max(r.percentage for r in results), 1)
        
    total_tab_switches = sum(r.tab_switches for r in results)

    # Get latest saved resume for the resume card
    latest_resume = Resume.objects.filter(user=request.user).first()

    return render(request, 'accounts/dashboard.html', {
        'results': results,
        'total_tests': total_tests,
        'average_accuracy': average_accuracy,
        'best_score': best_score,
        'total_tab_switches': total_tab_switches,
        'latest_resume': latest_resume,
    })


# ============ AI RESUME GENERATOR ============

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


def _call_groq(prompt, max_tokens=500, temperature=0.7):
    """Call Groq LLM API and return response text."""
    import urllib.request
    api_key = _get_groq_key()
    if not api_key:
        return None
    req = urllib.request.Request(
        'https://api.groq.com/openai/v1/chat/completions',
        data=json.dumps({
            "model": "llama-3.1-8b-instant",
            "messages": [
                {"role": "system", "content": "You are an expert career coach and resume writer. Follow instructions precisely. Output ONLY what is asked, no filler text."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": max_tokens,
            "temperature": temperature
        }).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}',
            'User-Agent': 'Mozilla/5.0'
        }
    )
    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read().decode('utf-8'))
        return result['choices'][0]['message']['content'].strip()


def _build_resume_context(data):
    """Build a flat text representation of the resume for AI prompts."""
    parts = []
    b = data.get('basics', {})
    if b.get('name'): parts.append(f"Name: {b['name']}")
    if b.get('summary'): parts.append(f"Summary: {b['summary']}")
    sk = data.get('skills', {})
    if sk.get('technical'): parts.append(f"Technical Skills: {', '.join(sk['technical'])}")
    if sk.get('soft'): parts.append(f"Soft Skills: {', '.join(sk['soft'])}")
    for exp in data.get('experience', []):
        parts.append(f"Experience: {exp.get('designation','')} at {exp.get('company','')} ({exp.get('tenure','')}) - {exp.get('description','')}")
    for edu in data.get('education', []):
        parts.append(f"Education: {edu.get('degree','')} from {edu.get('institution','')} ({edu.get('year','')})")
    for proj in data.get('projects', []):
        parts.append(f"Project: {proj.get('name','')} - {proj.get('description','')}")
    return '\n'.join(parts)


def resume_editor(request):
    """Main resume editor page with live preview."""
    data = Resume.get_default_json()
    brand_color = '#6366f1'
    style = 'modernist'

    # Load previously saved resume if authenticated
    if request.user.is_authenticated:
        saved = Resume.objects.filter(user=request.user).first()
        if saved and saved.resume_json:
            data = saved.resume_json
            brand_color = saved.brand_color or '#6366f1'
            style = saved.style_choice or 'modernist'
        else:
            # Pre-fill from user profile
            data['basics']['name'] = request.user.name or ''
            data['basics']['email'] = request.user.email or ''
            data['basics']['phone'] = request.user.phone or ''

    return render(request, 'accounts/resume_base.html', {
        'data': data,
        'data_json': json.dumps(data),
        'brand_color': brand_color,
        'initial_style': style,
    })


@csrf_exempt
def resume_preview_fragment(request):
    """Return rendered HTML fragment for the selected template."""
    if request.method != 'POST':
        return HttpResponse('', status=400)
    body = json.loads(request.body)
    style = body.get('style', 'modernist')
    data = body.get('data', Resume.get_default_json())
    brand_color = body.get('brand_color', '#6366f1')

    template_map = {
        'modernist': 'accounts/themes/modernist.html',
        'executive': 'accounts/themes/executive.html',
        'creative': 'accounts/themes/creative.html',
    }
    tpl = template_map.get(style, template_map['modernist'])
    html = render_to_string(tpl, {'data': data, 'brand_color': brand_color}, request=request)
    return HttpResponse(html)


@csrf_exempt
def resume_ai_summary(request):
    """Generate AI professional summary from resume data."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid'}, status=400)
    data = json.loads(request.body)
    context = _build_resume_context(data)
    prompt = f"""Based on this resume data, write a compelling 3-4 line professional summary:

{context}

CRITICAL: Output ONLY the summary paragraph. No bullet points, no headers, no intro text."""

    try:
        summary = _call_groq(prompt, max_tokens=200)
        return JsonResponse({'summary': summary or 'Could not generate summary.'})
    except Exception as e:
        return JsonResponse({'summary': f'Error: {str(e)}'})


@csrf_exempt
def resume_ats_match(request):
    """ATS Matcher: Compare resume against job description."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid'}, status=400)
    body = json.loads(request.body)
    resume_data = body.get('resume_data', {})
    jd = body.get('job_description', '')
    context = _build_resume_context(resume_data)

    prompt = f"""You are an ATS (Applicant Tracking System) analyzer. Compare this resume against the job description.

RESUME:
{context}

JOB DESCRIPTION:
{jd}

Respond in EXACT JSON format (no markdown, no extra text):
{{"score": <number 0-100>, "keywords_found": ["keyword1","keyword2",...], "keywords_missing": ["keyword1","keyword2",...]}}"""

    try:
        result_text = _call_groq(prompt, max_tokens=400, temperature=0.3)
        # Parse JSON from response
        result_text = result_text.strip()
        if result_text.startswith('```'): 
            result_text = result_text.split('\n', 1)[1].rsplit('```', 1)[0]
        result = json.loads(result_text)
        return JsonResponse(result)
    except Exception as e:
        return JsonResponse({'score': 0, 'keywords_found': [], 'keywords_missing': [], 'error': str(e)})


@csrf_exempt
def resume_tone_adjust(request):
    """Tone Adjustment: Rephrase summary and experience based on slider position."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid'}, status=400)
    body = json.loads(request.body)
    resume_data = body.get('resume_data', {})
    tone_val = int(body.get('tone', 50))

    if tone_val < 30:
        tone_desc = "very formal, corporate, conservative, executive-level"
    elif tone_val < 50:
        tone_desc = "professional, polished, business-appropriate"
    elif tone_val < 70:
        tone_desc = "modern, confident, balanced between professional and dynamic"
    else:
        tone_desc = "energetic, startup-friendly, dynamic, action-oriented, bold"

    summary = resume_data.get('basics', {}).get('summary', '')
    experiences = [e.get('description', '') for e in resume_data.get('experience', [])]

    prompt = f"""Rewrite the following resume content with this tone: {tone_desc}

SUMMARY (rewrite this):
{summary}

EXPERIENCE DESCRIPTIONS (rewrite each, separated by |||):
{'|||'.join(experiences)}

Respond in EXACT JSON (no markdown):
{{"summary": "rewritten summary", "experience": ["desc1", "desc2", ...]}}"""

    try:
        result_text = _call_groq(prompt, max_tokens=600, temperature=0.7)
        if result_text.startswith('```'):
            result_text = result_text.split('\n', 1)[1].rsplit('```', 1)[0]
        result = json.loads(result_text)
        return JsonResponse(result)
    except Exception as e:
        return JsonResponse({'error': str(e)})


@csrf_exempt
def resume_star_polish(request):
    """STAR Method Polisher: Rewrite text using Situation-Task-Action-Result."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid'}, status=400)
    body = json.loads(request.body)
    text = body.get('text', '')

    prompt = f"""Rewrite this resume bullet point using the STAR method (Situation, Task, Action, Result) to make it impactful and quantified:

Original: {text}

CRITICAL: Output ONLY the rewritten bullet point. Keep it to 2-3 concise sentences. Include metrics/numbers where possible. No labels like "Situation:" etc."""

    try:
        polished = _call_groq(prompt, max_tokens=200, temperature=0.7)
        return JsonResponse({'polished': polished or text})
    except Exception as e:
        return JsonResponse({'polished': text, 'error': str(e)})


@csrf_exempt
def resume_recommend_skills(request):
    """Recommend skills based on resume summary, experience, and projects."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid'}, status=400)
    body = json.loads(request.body)
    data = body.get('resume_data', {})
    context = _build_resume_context(data)

    prompt = f"""Analyze the following resume data and recommend 8-10 highly relevant skills (both technical and soft) that the user might have missed or should include:

{context}

Respond in EXACT JSON format:
{{"technical": ["skill1", "skill2", ...], "soft": ["skill1", "skill2", ...]}}"""

    try:
        result_text = _call_groq(prompt, max_tokens=300, temperature=0.7)
        if result_text.startswith('```'):
            result_text = result_text.split('\n', 1)[1].rsplit('```', 1)[0]
        result = json.loads(result_text)
        return JsonResponse(result)
    except Exception as e:
        return JsonResponse({'technical': [], 'soft': [], 'error': str(e)})


@csrf_exempt
@login_required
def resume_save(request):
    """Save resume JSON to database."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid'}, status=400)
    body = json.loads(request.body)
    style = body.get('style', 'modernist')
    data = body.get('data', {})
    brand_color = body.get('brand_color', '#6366f1')

    resume, created = Resume.objects.update_or_create(
        user=request.user,
        defaults={
            'title': data.get('basics', {}).get('name', 'My Resume') + "'s Resume",
            'style_choice': style,
            'resume_json_text': json.dumps(data),
            'brand_color': brand_color,
        }
    )
    return JsonResponse({'status': 'success', 'id': resume.id})


@login_required
def resume_download_pdf(request):
    """Fallback view that renders the base for print-only triggers."""
    saved = Resume.objects.filter(user=request.user).first()
    if not saved or not saved.resume_json:
        return redirect('resume_editor')
    return render(request, 'accounts/resume_base.html', {
        'data': saved.resume_json,
        'brand_color': saved.brand_color or '#6366f1',
        'initial_style': saved.style_choice or 'modernist',
    })

