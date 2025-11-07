"""
Conversation chatbot service using Google Generative API and Redis for session memory.

This provides a lightweight session memory stored in Redis and two methods:
- start_session(user) -> (session_id, assistant_text)
- send_message(session_id, user_message) -> assistant_text

Notes:
- Requires `google-generative-ai` (genai) and `redis` packages and settings.GEMINI_API_KEY and settings.REDIS_URL.
"""
import json
import uuid
from datetime import datetime, timedelta

import google.generativeai as genai
import redis
from django.conf import settings

from .ai_insights import AIInsightsService
from .time_series_analyzer import TimeSeriesAnalyzer, ForecastEngine
from finance.models import RecurringPayment, UserProfile


genai.configure(api_key=getattr(settings, 'GEMINI_API_KEY', None))


class ChatbotService:
    def __init__(self):
        # model name can be tuned via settings if required
        self.model_name = getattr(settings, 'GEMINI_MODEL', 'gemini-1.0')
        self.redis = redis.from_url(getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0'), decode_responses=True)
        # helper insights service for reusing context builders
        self.insights = AIInsightsService()
        # initialize the generative model similar to AIInsightsService
        try:
            self.model = genai.GenerativeModel(getattr(settings, 'GEMINI_MODEL', 'gemini-flash-latest'))
        except Exception:
            # fallback: no model instance available
            self.model = None

    def _redis_key(self, session_id: str) -> str:
        return f"chat:{session_id}:messages"

    def _meta_key(self, session_id: str) -> str:
        return f"chat:{session_id}:meta"

    def build_context(self, user):
        """Return textual context and a small meta dict built from user's data.

        This re-uses the AIInsightsService context builder where appropriate.
        """
        # try to reuse AIInsightsService helper if available
        try:
            ctx = self.insights._build_user_context(user)
            # _build_user_context in AIInsightsService typically returns a dict; create text summary
            text_lines = []
            # include profile goal
            profile = None
            try:
                profile = UserProfile.objects.get(user=user)
            except UserProfile.DoesNotExist:
                profile = None

            if profile:
                text_lines.append(f"Savings goal: ${float(profile.monthly_savings_goal):.2f}")
                if profile.financial_goal_description:
                    text_lines.append(f"Goal note: {profile.financial_goal_description}")

            # include quick category and totals if present in ctx
            total = ctx.get('total_spending') or ctx.get('total_spent') or 0
            text_lines.append(f"Total spending (period): ${float(total):.2f}")

            categories = ctx.get('category_spending') or {}
            if categories:
                text_lines.append("Category breakdown:")
                for k, v in sorted(categories.items(), key=lambda x: x[1], reverse=True):
                    text_lines.append(f" - {k}: ${float(v):.2f}")

            recurring = ctx.get('recurring_payments') or []
            if recurring:
                text_lines.append("Recurring payments:")
                for r in recurring:
                    name = r.get('name') or r.get('description') or 'n/a'
                    amt = r.get('amount') or 0
                    freq = r.get('frequency', 'unknown')
                    text_lines.append(f" - {name}: ${float(amt):.2f} ({freq})")

            anomalies = ctx.get('anomalies') or []
            text_lines.append(f"Anomalies detected: {len(anomalies)}")

            text = "\n".join(text_lines)
            meta = ctx
            return text, meta
        except Exception:
            # Fallback simple context if anything fails
            try:
                profile = UserProfile.objects.get(user=user)
                savings_goal = float(profile.monthly_savings_goal)
            except Exception:
                savings_goal = 0.0
            text = f"User: {user.username}\nSavings goal: ${savings_goal:.2f}\nNo detailed context available."
            return text, {"savings_goal": savings_goal}

    def start_session(self, user):
        session_id = str(uuid.uuid4())
        context_text, context_meta = self.build_context(user)

        meta = {
            "user_id": user.id,
            "started_at": datetime.utcnow().isoformat(),
            "context_text": context_text,
            "context_meta": context_meta,
        }
        # Ensure non-serializable values (dates, Decimals) are converted to strings
        self.redis.set(self._meta_key(session_id), json.dumps(meta, default=str))

        system_prompt = (
            "You are FinSIGHT's financial assistant. Use the user context to produce a short 5-8 line summary and 2-3 actionable recommendations."
        )
        prompt = f"{system_prompt}\n\nUSER CONTEXT:\n{context_text}\n\nPlease provide a concise summary and 2 recommended actions."

        assistant_text = "Sorry — unable to generate AI response right now."
        try:
            if self.model is not None:
                resp = self.model.generate_content(prompt)
                assistant_text = resp.text
            else:
                assistant_text = "AI model not available"
        except Exception as e:
            assistant_text = f"AI generation error: {e}"

        # store messages: system, context, assistant
        self.redis.rpush(self._redis_key(session_id), json.dumps({"role": "system", "text": system_prompt, "ts": datetime.utcnow().isoformat()}))
        self.redis.rpush(self._redis_key(session_id), json.dumps({"role": "context", "text": context_text, "ts": datetime.utcnow().isoformat()}))
        self.redis.rpush(self._redis_key(session_id), json.dumps({"role": "assistant", "text": assistant_text, "ts": datetime.utcnow().isoformat()}))

        return session_id, assistant_text

    def send_message(self, session_id: str, user_message: str) -> str:
        key = self._redis_key(session_id)
        meta_json = self.redis.get(self._meta_key(session_id))
        if not meta_json:
            raise ValueError("Session not found")

        meta = json.loads(meta_json)
        # append user message
        self.redis.rpush(key, json.dumps({"role": "user", "text": user_message, "ts": datetime.utcnow().isoformat()}))

        # prepare sliding window of messages
        raw = self.redis.lrange(key, -30, -1)
        convo = []
        for r in raw:
            try:
                m = json.loads(r)
                role = m.get('role', 'user')
                convo.append(f"{role.upper()}: {m.get('text','')}")
            except Exception:
                continue

        system_intro = (
            "You are FinSIGHT's conversational financial assistant. Use the conversation and the provided user context to answer clearly and give actionable recommendations when relevant."
        )
        prompt = system_intro + "\n\nUSER CONTEXT:\n" + meta.get('context_text', '') + "\n\nCONVERSATION:\n" + "\n".join(convo) + "\n\nAssistant:" 

        assistant_text = "Sorry — failed to generate a reply."
        try:
            if self.model is not None:
                resp = self.model.generate_content(prompt)
                assistant_text = resp.text
            else:
                assistant_text = "AI model not available"
        except Exception as e:
            assistant_text = f"AI generation error: {e}"

        self.redis.rpush(key, json.dumps({"role": "assistant", "text": assistant_text, "ts": datetime.utcnow().isoformat()}))
        return assistant_text

    def get_history(self, session_id: str):
        raw = self.redis.lrange(self._redis_key(session_id), 0, -1)
        return [json.loads(x) for x in raw]

    def get_session_meta(self, session_id: str):
        raw = self.redis.get(self._meta_key(session_id))
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None


def get_chatbot_service():
    return ChatbotService()
