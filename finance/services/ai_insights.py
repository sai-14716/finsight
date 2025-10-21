# finance/services/ai_insights.py
"""
AI-powered financial insights using Google Gemini API.
"""

import google.generativeai as genai
from django.conf import settings
from typing import Dict, List
from datetime import datetime, timedelta

from finance.models import FinancialInsight, UserProfile, RecurringPayment
from .time_series_analyzer import TimeSeriesAnalyzer, ForecastEngine


class AIInsightsService:
    """Service for generating AI-powered financial insights"""
    
    def __init__(self):
        """Initialize Gemini API"""
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel('gemini-pro')
    
    def generate_monthly_insight(self, user) -> str:
        """
        Generate comprehensive monthly financial insight.
        
        Args:
            user: Django User object
        
        Returns:
            AI-generated insight text
        """
        # Gather user data
        context = self._build_user_context(user)
        
        # Build prompt
        prompt = self._build_monthly_insight_prompt(context)
        
        # Generate insight
        try:
            response = self.model.generate_content(prompt)
            insight_text = response.text
            
            # Save insight to database
            FinancialInsight.objects.create(
                user=user,
                insight_text=insight_text,
                insight_type='monthly_summary'
            )
            
            return insight_text
        
        except Exception as e:
            print(f"Error generating insight: {e}")
            return self._generate_fallback_insight(context)
    
    def generate_anomaly_alert(self, user, anomalies: List[Dict]) -> str:
        """
        Generate insight about unusual spending patterns.
        
        Args:
            user: Django User object
            anomalies: List of detected anomalies
        
        Returns:
            AI-generated alert text
        """
        if not anomalies:
            return ""
        
        context = self._build_anomaly_context(user, anomalies)
        prompt = self._build_anomaly_prompt(context)
        
        try:
            response = self.model.generate_content(prompt)
            insight_text = response.text
            
            FinancialInsight.objects.create(
                user=user,
                insight_text=insight_text,
                insight_type='anomaly_alert'
            )
            
            return insight_text
        
        except Exception as e:
            print(f"Error generating anomaly alert: {e}")
            return f"We noticed {len(anomalies)} unusual spending day(s) in your recent transactions. Review your spending to ensure everything looks correct."
    
    def _build_user_context(self, user) -> Dict:
        """Build comprehensive context about user's finances"""
        # Get user profile
        try:
            profile = UserProfile.objects.get(user=user)
            savings_goal = float(profile.monthly_savings_goal)
            goal_description = profile.financial_goal_description or "Save money"
        except UserProfile.DoesNotExist:
            savings_goal = 0
            goal_description = "Save money"
        
        # Get spending analysis
        analyzer = TimeSeriesAnalyzer(user)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        analyzer.load_data(start_date=start_date, end_date=end_date)
        
        # Category breakdown
        if analyzer.df is not None and len(analyzer.df) > 0:
            category_spending = analyzer.df.groupby('category')['amount'].sum().to_dict()
            total_spending = analyzer.df['amount'].sum()
        else:
            category_spending = {}
            total_spending = 0
        
        # Get forecast
        forecast_engine = ForecastEngine(user)
        forecast = forecast_engine.forecast_next_month()
        
        # Get recurring payments
        recurring_payments = RecurringPayment.objects.filter(
            user=user,
            is_active=True,
            confirmed_by_user=True
        )
        
        recurring_list = [
            {
                'name': p.name,
                'amount': float(p.amount),
                'frequency': p.frequency
            }
            for p in recurring_payments
        ]
        
        # Detect anomalies
        anomalies = analyzer.detect_anomalies()
        
        # Calculate threshold
        threshold_info = analyzer.calculate_spending_threshold()
        
        return {
            'user_name': user.first_name or user.username,
            'savings_goal': savings_goal,
            'goal_description': goal_description,
            'total_spending_last_30_days': float(total_spending),
            'category_spending': {k: float(v) for k, v in category_spending.items()},
            'forecast': forecast,
            'recurring_payments': recurring_list,
            'anomalies': anomalies,
            'avg_daily_spending': threshold_info['avg_daily_spending'],
            'unusual_threshold': threshold_info['threshold']
        }
    
    def _build_monthly_insight_prompt(self, context: Dict) -> str:
        """Build prompt for monthly insight generation"""
        prompt = f"""You are a helpful, encouraging financial advisor for FinSIGHT, a personal finance app.

User Context:
- Name: {context['user_name']}
- Financial Goal: {context['goal_description']} (${context['savings_goal']}/month)
- Last 30 Days Spending: ${context['total_spending_last_30_days']:.2f}
- Average Daily Discretionary Spending: ${context['avg_daily_spending']:.2f}

Spending Breakdown by Category:"""
        
        for category, amount in sorted(context['category_spending'].items(), key=lambda x: x[1], reverse=True):
            prompt += f"\n  - {category}: ${amount:.2f}"
        
        prompt += f"\n\nNext Month Forecast:"
        prompt += f"\n  - Total Projected Spending: ${context['forecast']['total_forecast']:.2f}"
        prompt += f"\n  - Recurring Payments: ${context['forecast']['deterministic_spend']:.2f}"
        prompt += f"\n  - Projected Discretionary: ${context['forecast']['projected_discretionary']:.2f}"
        
        if context['recurring_payments']:
            prompt += f"\n\nConfirmed Recurring Payments:"
            for payment in context['recurring_payments']:
                prompt += f"\n  - {payment['name']}: ${payment['amount']:.2f} ({payment['frequency']})"
        
        if context['anomalies']:
            prompt += f"\n\nUnusual Spending Days (last 30 days): {len(context['anomalies'])}"
            for anomaly in context['anomalies'][:3]:  # Top 3
                prompt += f"\n  - {anomaly['date'].strftime('%b %d')}: ${anomaly['amount']:.2f} (avg: ${anomaly['mean']:.2f})"
        
        prompt += """

Task: Generate a concise, encouraging, and actionable financial insight (2-3 paragraphs, max 150 words). Include:
1. Brief assessment of their spending vs. goal
2. One specific, actionable recommendation based on their data
3. Encouragement and positive reinforcement

Keep the tone friendly, supportive, and conversational. Avoid jargon. Be specific using their actual numbers."""
        
        return prompt
    
    def _build_anomaly_context(self, user, anomalies: List[Dict]) -> Dict:
        """Build context for anomaly alerts"""
        return {
            'user_name': user.first_name or user.username,
            'anomalies': anomalies[:5],  # Top 5 anomalies
            'count': len(anomalies)
        }
    
    def _build_anomaly_prompt(self, context: Dict) -> str:
        """Build prompt for anomaly alert generation"""
        prompt = f"""You are a financial advisor alerting {context['user_name']} about unusual spending patterns.

Detected Unusual Spending:"""
        
        for anomaly in context['anomalies']:
            date_str = anomaly['date'].strftime('%B %d')
            prompt += f"\n  - {date_str}: ${anomaly['amount']:.2f} (typical: ${anomaly['mean']:.2f})"
        
        prompt += """

Task: Write a brief, friendly alert (2-3 sentences, max 50 words) that:
1. Notes the unusual spending without being alarmist
2. Suggests reviewing those transactions
3. Keeps a helpful, non-judgmental tone

Be concise and supportive."""
        
        return prompt
    
    def _generate_fallback_insight(self, context: Dict) -> str:
        """Generate a basic insight when AI is unavailable"""
        total = context['total_spending_last_30_days']
        goal = context['savings_goal']
        forecast = context['forecast']['total_forecast']
        
        if goal > 0:
            if total < goal:
                return f"Great job! Your spending last month (${total:.2f}) was under your savings goal. Next month's forecast is ${forecast:.2f}. Keep up the excellent work managing your finances!"
            else:
                top_category = max(context['category_spending'].items(), key=lambda x: x[1])[0] if context['category_spending'] else 'discretionary spending'
                return f"You spent ${total:.2f} last month, which is above your ${goal:.2f} savings goal. Your largest expense was {top_category}. Consider setting a budget for this category to help meet your goal next month."
        else:
            return f"Your total spending last month was ${total:.2f}. Next month's forecast is ${forecast:.2f}. Set a savings goal in your profile to get personalized recommendations!"


# Utility function
def get_ai_insights_service() -> AIInsightsService:
    """Get an instance of AIInsightsService"""
    return AIInsightsService()