"""
services.py — The Brain of the AI Career Coach.

Aggregates all user data (tests, resume, profile) into a structured
"Context Profile" that is injected into every LLM prompt so the AI
can give data-informed, personalized coaching.
"""

import json
from .models import TestResult, Resume, ChatMessage


class UserContextService:
    """Builds a comprehensive user snapshot for AI context injection."""

    def __init__(self, user):
        self.user = user

    # ── Data Fetchers ────────────────────────────────────

    def get_profile_summary(self):
        """Basic profile info."""
        u = self.user
        return {
            "name": u.name or "Unknown",
            "email": u.email,
            "branch": u.branch or "Not specified",
            "education": u.education or "Not specified",
            "phone": u.phone or "",
            "registration": u.registration or "",
        }

    def get_recent_tests(self, limit=5):
        """Last N test results with computed metadata."""
        results = TestResult.objects.filter(
            user=self.user
        ).select_related('subject').order_by('-date')[:limit]

        tests = []
        for r in results:
            tests.append({
                "subject": r.subject.name,
                "category": r.subject.category,
                "score": r.score,
                "total": r.total_questions,
                "percentage": round(r.percentage, 1),
                "time_taken_mins": round(r.time_taken / 60, 1) if r.time_taken else 0,
                "violations": r.violations,
                "tab_switches": r.tab_switches,
                "auto_submitted": r.auto_submitted,
                "date": r.date.strftime("%b %d, %Y") if r.date else "",
            })
        return tests

    def get_test_analytics(self):
        """Aggregate test performance analytics."""
        all_results = TestResult.objects.filter(user=self.user)
        if not all_results.exists():
            return None

        total = all_results.count()
        avg_pct = sum(r.percentage for r in all_results) / total
        best = max(r.percentage for r in all_results)
        worst = min(r.percentage for r in all_results)
        total_violations = sum(r.tab_switches for r in all_results)

        # Category-wise breakdown
        category_scores = {}
        for r in all_results.select_related('subject'):
            cat = r.subject.category
            if cat not in category_scores:
                category_scores[cat] = []
            category_scores[cat].append(r.percentage)

        category_avg = {
            cat: round(sum(scores) / len(scores), 1)
            for cat, scores in category_scores.items()
        }

        # Subject-wise weaknesses (below 50%)
        weak_subjects = []
        subject_scores = {}
        for r in all_results.select_related('subject'):
            subj = r.subject.name
            if subj not in subject_scores:
                subject_scores[subj] = []
            subject_scores[subj].append(r.percentage)

        for subj, scores in subject_scores.items():
            avg = sum(scores) / len(scores)
            if avg < 50:
                weak_subjects.append({"subject": subj, "avg_score": round(avg, 1)})

        return {
            "total_tests": total,
            "average_accuracy": round(avg_pct, 1),
            "best_score": round(best, 1),
            "worst_score": round(worst, 1),
            "total_tab_switches": total_violations,
            "category_averages": category_avg,
            "weak_subjects": weak_subjects,
        }

    def get_resume_snapshot(self):
        """Extract key resume data for AI context."""
        resume = Resume.objects.filter(user=self.user).first()
        if not resume:
            return None

        data = resume.resume_json
        if not data:
            return None

        basics = data.get("basics", {})
        skills = data.get("skills", {})
        experience = data.get("experience", [])
        education = data.get("education", [])
        projects = data.get("projects", [])
        certifications = data.get("certifications", [])

        return {
            "has_resume": True,
            "name": basics.get("name", ""),
            "summary": basics.get("summary", ""),
            "technical_skills": skills.get("technical", []),
            "soft_skills": skills.get("soft", []),
            "experience_count": len(experience),
            "experience_roles": [
                f"{e.get('designation', '')} at {e.get('company', '')}"
                for e in experience if e.get('company')
            ],
            "education_list": [
                f"{e.get('degree', '')} from {e.get('institution', '')}"
                for e in education if e.get('degree')
            ],
            "project_count": len(projects),
            "project_names": [p.get("name", "") for p in projects if p.get("name")],
            "certifications": certifications,
            "ats_score": resume.ats_score,
        }

    def get_chat_history(self, limit=10):
        """Last N chat messages for conversation continuity."""
        msgs = ChatMessage.objects.filter(
            user=self.user
        ).order_by('-created_at')[:limit]
        # Return in chronological order
        return [
            {"role": m.role, "content": m.content}
            for m in reversed(msgs)
        ]

    # ── Main Context Builder ─────────────────────────────

    def build_context_profile(self):
        """
        Build the complete user context profile string that gets
        prepended to every AI prompt as system context.
        """
        profile = self.get_profile_summary()
        tests = self.get_recent_tests()
        analytics = self.get_test_analytics()
        resume = self.get_resume_snapshot()

        sections = []

        # Profile
        sections.append(f"""## USER PROFILE
- Name: {profile['name']}
- Email: {profile['email']}
- Branch: {profile['branch']}
- Education Level: {profile['education']}""")

        # Resume
        if resume:
            skills_str = ", ".join(resume["technical_skills"][:10]) if resume["technical_skills"] else "None listed"
            soft_str = ", ".join(resume["soft_skills"][:5]) if resume["soft_skills"] else "None listed"
            roles_str = "; ".join(resume["experience_roles"][:3]) if resume["experience_roles"] else "No experience listed"
            edu_str = "; ".join(resume["education_list"][:3]) if resume["education_list"] else "Not listed"
            proj_str = ", ".join(resume["project_names"][:5]) if resume["project_names"] else "None"
            certs_str = ", ".join(resume["certifications"][:5]) if resume["certifications"] else "None"

            sections.append(f"""## RESUME DATA
- Summary: {resume['summary'][:200] or 'No summary written'}
- Technical Skills: {skills_str}
- Soft Skills: {soft_str}
- Experience ({resume['experience_count']} roles): {roles_str}
- Education: {edu_str}
- Projects ({resume['project_count']}): {proj_str}
- Certifications: {certs_str}
- ATS Score: {resume['ats_score']}%""")
        else:
            sections.append("## RESUME DATA\n⚠ The user has NOT created a resume yet.")

        # Test Analytics
        if analytics:
            weak_str = ", ".join(
                f"{w['subject']} ({w['avg_score']}%)"
                for w in analytics["weak_subjects"]
            ) if analytics["weak_subjects"] else "None (all above 50%)"

            cat_str = ", ".join(
                f"{cat}: {avg}%"
                for cat, avg in analytics["category_averages"].items()
            )

            sections.append(f"""## TEST PERFORMANCE
- Total Tests Taken: {analytics['total_tests']}
- Average Accuracy: {analytics['average_accuracy']}%
- Best Score: {analytics['best_score']}% | Worst: {analytics['worst_score']}%
- Category Averages: {cat_str}
- Weak Subjects (below 50%): {weak_str}
- Total Tab Switches (integrity flag): {analytics['total_tab_switches']}""")
        else:
            sections.append("## TEST PERFORMANCE\n⚠ The user has NOT taken any tests yet.")

        # Recent Tests
        if tests:
            test_lines = []
            for t in tests[:3]:
                test_lines.append(
                    f"  - {t['subject']} ({t['category']}): {t['percentage']}% "
                    f"({t['score']}/{t['total']}) on {t['date']}"
                )
            sections.append("## RECENT TESTS\n" + "\n".join(test_lines))

        # Gap Analysis
        gaps = self._identify_gaps(analytics, resume)
        if gaps:
            sections.append("## IDENTIFIED GAPS\n" + "\n".join(f"- {g}" for g in gaps))

        return "\n\n".join(sections)

    # ── Insight Engine ───────────────────────────────────

    def _identify_gaps(self, analytics, resume):
        """Proactive gap identification for coaching suggestions."""
        gaps = []

        if not resume:
            gaps.append("🔴 NO RESUME: User hasn't created a resume. Suggest building one immediately.")

        if not analytics:
            gaps.append("🔴 NO TESTS: User hasn't taken any assessments. Suggest starting with a placement test.")
            return gaps

        # High test scores but low/no ATS score
        if analytics and resume:
            if analytics["average_accuracy"] > 70 and resume["ats_score"] < 50:
                gaps.append(
                    "🟡 MISMATCH: Strong test performance but weak ATS score. "
                    "Resume needs keyword optimization."
                )

        # Weak subjects
        if analytics and analytics["weak_subjects"]:
            for w in analytics["weak_subjects"]:
                gaps.append(
                    f"🟠 WEAK AREA: {w['subject']} at {w['avg_score']}% — needs focused practice."
                )

        # Resume missing key sections
        if resume:
            if not resume["summary"]:
                gaps.append("🟡 RESUME GAP: No professional summary written.")
            if resume["experience_count"] == 0:
                gaps.append("🟡 RESUME GAP: No work experience listed.")
            if resume["project_count"] == 0:
                gaps.append("🟡 RESUME GAP: No projects listed — critical for freshers.")
            if not resume["certifications"]:
                gaps.append("🟡 RESUME GAP: No certifications listed.")

        # Test integrity issues
        if analytics and analytics["total_tab_switches"] > 5:
            gaps.append(
                f"🔴 INTEGRITY: {analytics['total_tab_switches']} tab switches detected across tests."
            )

        return gaps

    def get_available_actions(self):
        """Return actions the chatbot can trigger."""
        from .models import Subject
        subjects = list(Subject.objects.values_list('name', 'slug', 'category'))
        return {
            "available_tests": [
                {"name": name, "slug": slug, "category": cat}
                for name, slug, cat in subjects
            ],
            "can_edit_resume": True,
            "can_view_dashboard": True,
        }
