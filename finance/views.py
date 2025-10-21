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


# ============================================================================
# Authentication Views
# ============================================================================

def register_view(request):
    """User registration view"""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Create user profile
            UserProfile.objects.create(user=user)
            login(request, user)
            messages.success(request, 'Welcome to FinSIGHT! Your account has been created.')
            return redirect('dashboard')
    else:
        form = UserCreationForm()
    
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
def sync_transactions(request):
    """Sync transactions from Plaid"""
    plaid_service = get_plaid_service()
    
    force_sync = request.data.get('force_sync', False)
    result = plaid_service.sync_transactions(request.user, force_full_sync=force_sync)
    
    if result['success']:
        return Response(result)
    else:
        return Response(result, status=400)


# ============================================================================
# Analytics & EDA
# ============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def spending_analytics(request):
    """Get spending analytics data"""
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
            'data': {}
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


# ============================================================================
# Recurring Payments & Time Series Analysis
# ============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def detect_recurring_payments(request):
    """Run recurring payment detection"""
    analyzer = TimeSeriesAnalyzer(request.user)
    analyzer.load_data()
    
    patterns = analyzer.detect_recurring_patterns()
    
    # Create pending confirmations
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
    
    return Response({
        'success': True,
        'patterns_found': len(patterns),
        'patterns': patterns
    })


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
    analyzer = TimeSeriesAnalyzer(request.user)
    analyzer.load_data()
    
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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_forecast(request):
    """Get next month's financial forecast"""
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


# ============================================================================
# AI Insights
# ============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_insights(request):
    """Generate AI-powered financial insights"""
    ai_service = get_ai_insights_service()
    
    try:
        insight = ai_service.generate_monthly_insight(request.user)
        
        return Response({
            'success': True,
            'insight': insight
        })
    
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def insights_view(request):
    """View all insights"""
    insights = FinancialInsight.objects.filter(user=request.user).order_by('-created_at')[:20]
    
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
    forecast_engine = ForecastEngine(user)
    forecast = forecast_engine.forecast_next_month()
    
    # Convert dates
    forecast['forecast_period']['start'] = forecast['forecast_period']['start'].isoformat()
    forecast['forecast_period']['end'] = forecast['forecast_period']['end'].isoformat()
    for payment in forecast['payment_schedule']:
        payment['date'] = payment['date'].isoformat()
    
    # Get anomalies
    anomalies = analyzer.detect_anomalies()
    
    # Get threshold
    threshold_info = analyzer.calculate_spending_threshold()
    
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