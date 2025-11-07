# finance/views.py
"""
Django views and API endpoints for FinSIGHT.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from datetime import datetime, timedelta
import json

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import (Transaction, Category, UserProfile, RecurringPayment, 
                     PendingRecurringConfirmation, FinancialInsight)
from .forms import TransactionForm, UserProfileForm, RecurringPaymentForm
from .services.plaid_service import get_plaid_service
from .services.ai_insights import get_ai_insights_service
from .services.time_series_analyzer import TimeSeriesAnalyzer, ForecastEngine
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
import logging
from .services.chatbot_service import get_chatbot_service
import google.generativeai as genai
from django.conf import settings

logger = logging.getLogger(__name__)

# Chatbot service (singleton)
chat_service = get_chatbot_service()


# ============================================================================
# Authentication Views
# ============================================================================

def register_view(request):
    """User registration view"""
    print("Recieved the form")
    if request.method == 'POST':
        print("Form is POST")
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Create user profile
            UserProfile.objects.create(user=user)
            login(request, user)
            messages.success(request, 'Welcome to FinSIGHT! Your account has been created.')
            return redirect('dashboard')
        else:
            print("Form is not valid")
            messages.error(request, 'Please correct the errors below.')
    else:
        print("Form is GET")
        form = UserCreationForm()
        messages.error(request, 'Wrong API Call.')
    return render(request, 'finance/register.html', {'form': form})


def login_view(request):
    """User login view"""
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('dashboard')
    else:
        form = AuthenticationForm()
    
    return render(request, 'finance/login.html', {'form': form})


@login_required
def logout_view(request):
    """User logout view"""
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('login')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ai_chat_start(request):
    print("Start a new chat session for the authenticated user and return initial AI insight")
    try:
        session_id, initial_text = chat_service.start_session(request.user)
        return Response({"session_id": session_id, "initial": initial_text})
    except Exception as e:
        logger.exception("Failed to start AI chat session")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ai_chat_message(request, session_id):
    """Send a user message to an existing chat session and return assistant reply."""
    message = request.data.get('message')
    if not message:
        return Response({"error": "No message provided"}, status=status.HTTP_400_BAD_REQUEST)
    try:
        # ownership check: ensure session belongs to requesting user
        meta = chat_service.get_session_meta(session_id)
        if not meta:
            return Response({"error": "Session not found"}, status=status.HTTP_404_NOT_FOUND)
        if meta.get('user_id') != request.user.id:
            return Response({"error": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        resp_text = chat_service.send_message(session_id, message)
        return Response({"response": resp_text})
    except ValueError:
        return Response({"error": "Session not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.exception("AI chat message handling failed")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ai_chat_summarize(request, session_id):
    """Generate a conversation summary and suggested goal updates for the session."""
    try:
        meta = chat_service.get_session_meta(session_id)
        if not meta:
            return Response({"error": "Session not found"}, status=status.HTTP_404_NOT_FOUND)
        if meta.get('user_id') != request.user.id:
            return Response({"error": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        history = chat_service.get_history(session_id)
        # Build a compact transcript
        transcript = "\n".join([f"{m.get('role')}: {m.get('text')}" for m in history])

        prompt = (
            "You are FinSIGHT's assistant. Summarize the conversation and propose a single suggested change to the user's monthly savings goal (a numeric value) and an optional improvement to the goal description. "
            "Return a JSON object with fields: suggested_goal (number, or null), suggested_description (string or null), summary (short text)."
        )
        full_prompt = prompt + "\n\nTRANSCRIPT:\n" + transcript

        try:
            # use the chatbot service's model if available
            model = getattr(chat_service, 'model', None)
            if model is not None:
                resp = model.generate_content(full_prompt)
                text = resp.text
            else:
                text = "AI model not available"
        except Exception as e:
            text = f"AI generation error: {e}"

        # Try to parse JSON from AI; if fails, return raw text
        suggested = None
        try:
            # attempt to find a JSON object inside text
            import re
            m = re.search(r"\{.*\}", text, re.S)
            if m:
                suggested = json.loads(m.group(0))
        except Exception:
            suggested = None

        return Response({
            'success': True,
            'raw': text,
            'parsed': suggested
        })
    except Exception as e:
        logger.exception("Summarize failed")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ai_chat_apply_goals(request, session_id):
    """Apply suggested goal updates to the user's profile after confirmation.

    Expects JSON body: { "monthly_savings_goal": 123.45, "goal_description": "..." }
    """
    try:
        meta = chat_service.get_session_meta(session_id)
        if not meta:
            return Response({"error": "Session not found"}, status=status.HTTP_404_NOT_FOUND)
        if meta.get('user_id') != request.user.id:
            return Response({"error": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        data = request.data
        goal = data.get('monthly_savings_goal')
        desc = data.get('goal_description')

        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        changed = False
        if goal is not None:
            try:
                profile.monthly_savings_goal = float(goal)
                changed = True
            except Exception:
                return Response({"error": "Invalid goal value"}, status=status.HTTP_400_BAD_REQUEST)
        if desc is not None:
            profile.financial_goal_description = desc
            changed = True
        if changed:
            profile.save()
        return Response({"success": True, "changed": changed})
    except Exception as e:
        logger.exception("Apply goals failed")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    


# ============================================================================
# Dashboard & Main Views
# ============================================================================

@login_required
def dashboard_view(request):
    """Main dashboard view"""
    user = request.user
    
    # Get recent transactions
    recent_transactions = Transaction.objects.filter(user=user).order_by('-date')[:10]
    
    # Get pending confirmations
    pending_confirmations = PendingRecurringConfirmation.objects.filter(user=user)
    
    # Get latest insight
    latest_insight = FinancialInsight.objects.filter(user=user).first()
    
    # Get user profile
    profile = UserProfile.objects.get(user=user)
    
    context = {
        'recent_transactions': recent_transactions,
        'pending_confirmations': pending_confirmations,
        'latest_insight': latest_insight,
        'profile': profile,
    }
    
    return render(request, 'finance/dashboard.html', context)


@login_required
def profile_view(request):
    """User profile management view"""
    profile = UserProfile.objects.get(user=request.user)
    
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('profile')
    else:
        form = UserProfileForm(instance=profile)
    
    return render(request, 'finance/profile.html', {'form': form, 'profile': profile})


# ============================================================================
# Transaction Management
# ============================================================================

@login_required
def transactions_view(request):
    """List all transactions"""
    transactions = Transaction.objects.filter(user=request.user).order_by('-date')
    categories = Category.objects.all()
    
    context = {
        'transactions': transactions,
        'categories': categories,
    }
    
    return render(request, 'finance/transactions.html', context)


@login_required
def add_transaction_view(request):
    """Add manual transaction"""
    if request.method == 'POST':
        form = TransactionForm(request.POST)
        if form.is_valid():
            transaction = form.save(commit=False)
            transaction.user = request.user
            transaction.save()
            messages.success(request, 'Transaction added successfully!')
            return redirect('transactions')
    else:
        form = TransactionForm()
    
    return render(request, 'finance/add_transaction.html', {'form': form})


@login_required
@require_http_methods(["POST"])
def update_transaction_category(request, transaction_id):
    """Update transaction category (AJAX endpoint)"""
    transaction = get_object_or_404(Transaction, id=transaction_id, user=request.user)
    
    data = json.loads(request.body)
    category_id = data.get('category_id')
    
    if category_id:
        category = get_object_or_404(Category, id=category_id)
        transaction.category = category
        transaction.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Category updated successfully'
        })
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid category'
    }, status=400)


# ============================================================================
# Plaid Integration
# ============================================================================

@login_required
def plaid_link_view(request):
    """Initialize Plaid Link"""
    plaid_service = get_plaid_service()
    
    try:
        link_token = plaid_service.create_link_token(request.user)
        return render(request, 'finance/plaid_link.html', {'link_token': link_token})
    except Exception as e:
        messages.error(request, f'Error connecting to Plaid: {str(e)}')
        return redirect('dashboard')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def exchange_plaid_token(request):
    """Exchange public token for access token"""
    public_token = request.data.get('public_token')
    
    if not public_token:
        return Response({'error': 'No public token provided'}, status=400)
    
    plaid_service = get_plaid_service()
    
    try:
        access_token = plaid_service.exchange_public_token(public_token)
        
        # Save access token to user profile
        profile = UserProfile.objects.get(user=request.user)
        profile.plaid_access_token = access_token
        profile.save()
        
        return Response({'success': True, 'message': 'Account connected successfully'})
    
    except Exception as e:
        return Response({'error': str(e)}, status=500)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_sandbox_token(request):
    """
    [DEVELOPMENT ONLY]
    Creates a sandbox access token directly, bypassing Plaid Link.
    This is called by the 'Use Sandbox (Dev)' button.
    """
    try:
        service = get_plaid_service()
        
        # This service method creates and saves the sandbox token
        result = service.create_sandbox_access_token_for_user(request.user)
        
        if result.get('success'):
            return Response({
                'success': True,
                'message': 'Sandbox account created successfully.'
            }, status=status.HTTP_200_OK)
        else:
            # Service call failed (e.g., Plaid API error)
            return Response({
                'success': False,
                'error': result.get('error', 'Failed to create sandbox token.')
            }, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        # Catch any other unexpected errors
        logger.error(f"Error in create_sandbox_token view: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
# ------------------------------------

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sync_transactions(request):
    """Sync transactions from Plaid"""
    try:
        plaid_service = get_plaid_service()
        force_sync = request.data.get('force_sync', False)
        
        result = plaid_service.sync_transactions(request.user, force_full_sync=force_sync)
        
        if result['success']:
            return Response(result, status=status.HTTP_200_OK)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Sync error: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ============================================================================
# Analytics & EDA
# ============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def spending_analytics(request):
    """Get spending analytics data"""
    try:
        user = request.user
        
        # Get date range from query params
        days = int(request.query_params.get('days', 30))
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Initialize analyzer
        analyzer = TimeSeriesAnalyzer(user)
        analyzer.load_data(start_date=start_date, end_date=end_date)
        
        if analyzer.df is None or len(analyzer.df) == 0:
            return Response({
                'message': 'No transactions found for this period',
                'total_spending': 0,
                'transaction_count': 0,
                'category_spending': {},
                'daily_spending': [],
                'monthly_comparison': []
            })
        
        # Category breakdown
        category_spending = analyzer.df.groupby('category')['amount'].sum().to_dict()
        
        # Daily spending trend
        daily_spending = analyzer.df.groupby('date')['amount'].sum().reset_index()
        daily_spending['date'] = daily_spending['date'].astype(str)
        
        # Monthly comparison (last 6 months)
        monthly_data = []
        for i in range(6):
            month_start = (end_date - timedelta(days=30*i)).replace(day=1)
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            
            month_transactions = Transaction.objects.filter(
                user=user,
                date__gte=month_start,
                date__lte=month_end
            )
            
            total = sum(t.amount for t in month_transactions)
            monthly_data.append({
                'month': month_start.strftime('%b %Y'),
                'total': float(total)
            })
        
        monthly_data.reverse()
        
        return Response({
            'category_spending': {k: float(v) for k, v in category_spending.items()},
            'daily_spending': daily_spending.to_dict('records'),
            'monthly_comparison': monthly_data,
            'total_spending': float(analyzer.df['amount'].sum()),
            'transaction_count': len(analyzer.df)
        })
    except Exception as e:
        logger.error(f"Analytics error: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ============================================================================
# Recurring Payments & Time Series Analysis
# ============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def detect_recurring_payments(request):
    """Run recurring payment detection"""
    try:
        analyzer = TimeSeriesAnalyzer(request.user)
        analyzer.load_data()
        
        if analyzer.df is None or len(analyzer.df) == 0:
            return Response({
                'success': True,
                'patterns_found': 0,
                'patterns': [],
                'message': 'No transaction data available for analysis'
            })
        
        patterns = analyzer.detect_recurring_patterns()
        
        # Create pending confirmations
        created_count = 0
        for pattern in patterns:
            # Check if already exists
            exists = PendingRecurringConfirmation.objects.filter(
                user=request.user,
                description=pattern['description'],
                amount=pattern['amount']
            ).exists()
            
            if not exists:
                confirmation = PendingRecurringConfirmation.objects.create(
                    user=request.user,
                    description=pattern['description'],
                    amount=pattern['amount'],
                    frequency=pattern['frequency'],
                    confidence_score=pattern['confidence']
                )
                
                # Link related transactions
                transactions = Transaction.objects.filter(
                    id__in=pattern['transaction_ids']
                )
                confirmation.related_transactions.set(transactions)
                created_count += 1
        
        return Response({
            'success': True,
            'patterns_found': created_count,
            'patterns': patterns
        })
    except Exception as e:
        logger.error(f"Recurring detection error: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def confirm_recurring_payment(request, confirmation_id):
    """Confirm a pending recurring payment"""
    confirmation = get_object_or_404(
        PendingRecurringConfirmation,
        id=confirmation_id,
        user=request.user
    )
    
    action = request.data.get('action')  # 'confirm' or 'reject'
    
    if action == 'confirm':
        # Create recurring payment
        category = confirmation.related_transactions.first().category if confirmation.related_transactions.exists() else None
        
        # Determine due day based on frequency
        last_transaction = confirmation.related_transactions.order_by('-date').first()
        if confirmation.frequency == 'monthly':
            due_day = last_transaction.date.day
        elif confirmation.frequency in ['weekly', 'biweekly']:
            due_day = last_transaction.date.weekday()
        else:
            due_day = 1
        
        recurring_payment = RecurringPayment.objects.create(
            user=request.user,
            name=confirmation.description,
            amount=confirmation.amount,
            category=category,
            frequency=confirmation.frequency,
            due_day=due_day,
            start_date=last_transaction.date,
            auto_detected=True,
            confirmed_by_user=True
        )
        
        # Mark related transactions as recurring
        confirmation.related_transactions.update(
            is_recurring=True,
            recurring_frequency=confirmation.frequency
        )
        
        message = 'Recurring payment confirmed and added'
    else:
        message = 'Recurring payment rejected'
    
    # Delete confirmation
    confirmation.delete()
    
    return Response({
        'success': True,
        'message': message
    })


@login_required
def recurring_payments_view(request):
    """View and manage recurring payments"""
    recurring_payments = RecurringPayment.objects.filter(
        user=request.user,
        is_active=True
    )
    
    if request.method == 'POST':
        form = RecurringPaymentForm(request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.user = request.user
            payment.confirmed_by_user = True
            payment.save()
            messages.success(request, 'Recurring payment added!')
            return redirect('recurring_payments')
    else:
        form = RecurringPaymentForm()
    
    context = {
        'recurring_payments': recurring_payments,
        'form': form,
    }
    
    return render(request, 'finance/recurring_payments.html', context)


# ============================================================================
# Anomaly Detection & Forecast
# ============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detect_anomalies(request):
    """Detect spending anomalies"""
    try:
        analyzer = TimeSeriesAnalyzer(request.user)
        analyzer.load_data()
        
        if analyzer.df is None or len(analyzer.df) == 0:
            return Response({
                'success': True,
                'anomalies': [],
                'threshold_info': {},
                'anomaly_count': 0,
                'message': 'No transaction data available for analysis'
            })
        
        anomalies = analyzer.detect_anomalies()
        threshold_info = analyzer.calculate_spending_threshold()
        
        # Mark anomalies in database
        for anomaly in anomalies:
            for txn_data in anomaly['transactions']:
                Transaction.objects.filter(id=txn_data['id']).update(
                    is_anomaly=True,
                    anomaly_score=anomaly['z_score']
                )
        
        return Response({
            'success': True,
            'anomalies': anomalies,
            'threshold_info': threshold_info,
            'anomaly_count': len(anomalies)
        })
    except Exception as e:
        logger.error(f"Anomaly detection error: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_forecast(request):
    """Get next month's financial forecast"""
    try:
        forecast_engine = ForecastEngine(request.user)
        forecast = forecast_engine.forecast_next_month()
        
        # Convert dates to strings for JSON serialization
        forecast['forecast_period']['start'] = forecast['forecast_period']['start'].isoformat()
        forecast['forecast_period']['end'] = forecast['forecast_period']['end'].isoformat()
        
        for payment in forecast['payment_schedule']:
            payment['date'] = payment['date'].isoformat()
        
        return Response({
            'success': True,
            'forecast': forecast
        })
    except Exception as e:
        logger.error(f"Forecast error: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================================================
# AI Insights
# ============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_insights(request):
    """Generate AI-powered financial insights"""
    try:
        # Replace one-shot insight generation with chat-based initial insight
        session_id, initial_text = chat_service.start_session(request.user)
        return Response({
            'success': True,
            'session_id': session_id,
            'insight': initial_text
        })
    except Exception as e:
        logger.error(f"Insights generation error: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@login_required
def insights_view(request):
    """View all insights"""
    insights_ids = FinancialInsight.objects.filter(
        user=request.user
    ).order_by('-created_at').values_list('id', flat=True)[:20]

    insights = FinancialInsight.objects.filter(
        id__in=list(insights_ids)
    ).order_by('-created_at')
    # Mark as read
    insights.update(is_read=True)
    
    return render(request, 'finance/insights.html', {'insights': insights})


# ============================================================================
# API Endpoint for Full Dashboard Data
# ============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_data(request):
    """Get all dashboard data in one API call"""
    try:
        user = request.user
        
        # Get spending analytics
        analyzer = TimeSeriesAnalyzer(user)
        analyzer.load_data(start_date=datetime.now() - timedelta(days=30))
        
        if analyzer.df is not None and len(analyzer.df) > 0:
            category_spending = analyzer.df.groupby('category')['amount'].sum().to_dict()
            total_spending = float(analyzer.df['amount'].sum())
        else:
            category_spending = {}
            total_spending = 0
        
        # Get forecast
        try:
            forecast_engine = ForecastEngine(user)
            forecast = forecast_engine.forecast_next_month()
            
            # Convert dates
            forecast['forecast_period']['start'] = forecast['forecast_period']['start'].isoformat()
            forecast['forecast_period']['end'] = forecast['forecast_period']['end'].isoformat()
            for payment in forecast['payment_schedule']:
                payment['date'] = payment['date'].isoformat()
        except Exception as e:
            logger.warning(f"Forecast generation failed: {str(e)}")
            forecast = {
                'predicted_spending': 0,
                'forecast_period': {
                    'start': datetime.now().isoformat(),
                    'end': (datetime.now() + timedelta(days=30)).isoformat()
                },
                'breakdown': {'fixed_payments': 0, 'variable_spending': 0},
                'payment_schedule': []
            }
        
        # Get anomalies
        try:
            anomalies = analyzer.detect_anomalies()
            threshold_info = analyzer.calculate_spending_threshold()
        except Exception as e:
            logger.warning(f"Anomaly detection failed: {str(e)}")
            anomalies = []
            threshold_info = {}
        
        # Get profile
        profile = UserProfile.objects.get(user=user)
        
        # Get recent transactions
        recent_transactions = Transaction.objects.filter(user=user).order_by('-date')[:10]
        transactions_data = [
            {
                'id': t.id,
                'description': t.description,
                'amount': float(t.amount),
                'date': t.date.isoformat(),
                'category': t.category.name if t.category else 'Uncategorized',
                'is_recurring': t.is_recurring,
                'is_anomaly': t.is_anomaly
            }
            for t in recent_transactions
        ]
        
        # Get pending confirmations
        pending = PendingRecurringConfirmation.objects.filter(user=user)
        pending_data = [
            {
                'id': p.id,
                'description': p.description,
                'amount': float(p.amount),
                'frequency': p.frequency,
                'confidence': p.confidence_score
            }
            for p in pending
        ]
        
        # Get latest insight
        latest_insight = FinancialInsight.objects.filter(user=user).first()
        
        return Response({
            'profile': {
                'savings_goal': float(profile.monthly_savings_goal),
                'goal_description': profile.financial_goal_description,
                'last_sync': profile.last_sync_date.isoformat() if profile.last_sync_date else None
            },
            'spending': {
                'total_last_30_days': total_spending,
                'by_category': {k: float(v) for k, v in category_spending.items()}
            },
            'forecast': forecast,
            'anomalies': {
                'count': len(anomalies),
                'threshold': threshold_info,
                'recent': anomalies[:5]
            },
            'recent_transactions': transactions_data,
            'pending_confirmations': pending_data,
            'latest_insight': {
                'text': latest_insight.insight_text,
                'type': latest_insight.insight_type,
                'created_at': latest_insight.created_at.isoformat()
            } if latest_insight else None
        })
    except Exception as e:
        logger.error(f"Dashboard data error: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)