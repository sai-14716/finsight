# finance/urls.py
"""
URL configuration for FinSIGHT finance app.
"""

from django.urls import path
from . import views

urlpatterns = [
    # Authentication
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Dashboard & Profile
    path('', views.dashboard_view, name='dashboard'),
    path('profile/', views.profile_view, name='profile'),
    
    # Transactions
    path('transactions/', views.transactions_view, name='transactions'),
    path('transactions/add/', views.add_transaction_view, name='add_transaction'),
    path('transactions/<int:transaction_id>/update-category/', 
         views.update_transaction_category, name='update_transaction_category'),
    
    # Plaid Integration
    path('plaid/link/', views.plaid_link_view, name='plaid_link'),
    path('api/plaid/exchange-token/', views.exchange_plaid_token, name='exchange_plaid_token'),
    path('api/plaid/sync/', views.sync_transactions, name='sync_transactions'),
    
    # Analytics & Insights
    path('analytics/', views.transactions_view, name='analytics'),  # Reuse transactions template
    path('api/analytics/spending/', views.spending_analytics, name='spending_analytics'),
    path('api/analytics/anomalies/', views.detect_anomalies, name='detect_anomalies'),
    path('api/analytics/forecast/', views.get_forecast, name='get_forecast'),
    
    # Recurring Payments
    path('recurring/', views.recurring_payments_view, name='recurring_payments'),
    path('api/recurring/detect/', views.detect_recurring_payments, name='detect_recurring_payments'),
    path('api/recurring/<int:confirmation_id>/confirm/', 
         views.confirm_recurring_payment, name='confirm_recurring_payment'),
    
    # AI Insights
    path('insights/', views.insights_view, name='insights'),
    path('api/insights/generate/', views.generate_insights, name='generate_insights'),
    
    # Dashboard Data API
    path('api/dashboard/', views.dashboard_data, name='dashboard_data'),
]
'''
urlpatterns = [
    # Authentication
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Main views
    path('', views.login_view, name='dashboard'),
    path('profile/', views.profile_view, name='profile'),
    path('transactions/', views.transactions_view, name='transactions'),
    path('transactions/add/', views.add_transaction_view, name='add_transaction'),
    path('recurring-payments/', views.recurring_payments_view, name='recurring_payments'),
    path('insights/', views.insights_view, name='insights'),
    
    # Plaid integration
    path('plaid/link/', views.plaid_link_view, name='plaid_link'),
    
    # API endpoints
    path('api/plaid/exchange-token/', views.exchange_plaid_token, name='api_exchange_token'),
    path('api/transactions/sync/', views.sync_transactions, name='api_sync_transactions'),
    path('api/transactions/<int:transaction_id>/category/', views.update_transaction_category, name='api_update_category'),
    
    path('api/analytics/spending/', views.spending_analytics, name='api_spending_analytics'),
    path('api/analytics/anomalies/', views.detect_anomalies, name='api_detect_anomalies'),
    path('api/analytics/forecast/', views.get_forecast, name='api_forecast'),
    
    path('api/recurring/detect/', views.detect_recurring_payments, name='api_detect_recurring'),
    path('api/recurring/confirm/<int:confirmation_id>/', views.confirm_recurring_payment, name='api_confirm_recurring'),
    
    path('api/insights/generate/', views.generate_insights, name='api_generate_insights'),
    
    path('api/dashboard/', views.dashboard_data, name='api_dashboard_data'),
]
'''

# finsight/urls.py (Main project URLs)
"""
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', lambda request: redirect('dashboard'), name='home'),
    path('finance/', include('finance.urls')),
]
"""