from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal


class UserProfile(models.Model):
    """Extended user profile with financial goals and sync tracking"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    monthly_savings_goal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    financial_goal_description = models.TextField(blank=True, null=True)
    last_sync_date = models.DateTimeField(null=True, blank=True)
    plaid_access_token = models.CharField(max_length=255, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Profile: {self.user.username}"
    
    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"


class Category(models.Model):
    """Spending categories from Plaid or custom"""
    name = models.CharField(max_length=100, unique=True)
    plaid_category = models.CharField(max_length=200, blank=True, null=True)
    icon = models.CharField(max_length=50, default='💳')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ['name']


class Transaction(models.Model):
    """Individual financial transaction"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField()
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='transactions')
    
    # Recurring payment detection
    is_recurring = models.BooleanField(default=False)
    recurring_frequency = models.CharField(
        max_length=20, 
        choices=[
            ('weekly', 'Weekly'),
            ('biweekly', 'Bi-weekly'),
            ('monthly', 'Monthly'),
            ('quarterly', 'Quarterly'),
            ('annual', 'Annual')
        ],
        blank=True,
        null=True
    )
    
    # Plaid integration
    plaid_transaction_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    
    # Anomaly detection
    is_anomaly = models.BooleanField(default=False)
    anomaly_score = models.FloatField(null=True, blank=True)
    
    # Metadata
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.date} - {self.description}: ${self.amount}"
    
    class Meta:
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['user', 'date']),
            models.Index(fields=['user', 'is_recurring']),
            models.Index(fields=['category']),
        ]


class RecurringPayment(models.Model):
    """Manually added or confirmed recurring payments"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recurring_payments')
    name = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
    
    frequency = models.CharField(
        max_length=20,
        choices=[
            ('weekly', 'Weekly'),
            ('biweekly', 'Bi-weekly'),
            ('monthly', 'Monthly'),
            ('quarterly', 'Quarterly'),
            ('annual', 'Annual')
        ]
    )
    
    # For monthly: day of month (1-31)
    # For weekly: day of week (0-6, Monday=0)
    due_day = models.IntegerField()
    
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    auto_detected = models.BooleanField(default=False)
    confirmed_by_user = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} - ${self.amount} ({self.frequency})"
    
    class Meta:
        ordering = ['due_day', 'name']


class PendingRecurringConfirmation(models.Model):
    """Pending confirmations for auto-detected recurring payments"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pending_confirmations')
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    frequency = models.CharField(max_length=20)
    confidence_score = models.FloatField()
    
    # Related transactions that match this pattern
    related_transactions = models.ManyToManyField(Transaction, related_name='pending_confirmations')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Pending: {self.description} - ${self.amount}"
    
    class Meta:
        ordering = ['-confidence_score', '-created_at']


class FinancialInsight(models.Model):
    """AI-generated financial insights and recommendations"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='insights')
    insight_text = models.TextField()
    insight_type = models.CharField(
        max_length=50,
        choices=[
            ('monthly_summary', 'Monthly Summary'),
            ('anomaly_alert', 'Anomaly Alert'),
            ('savings_tip', 'Savings Tip'),
            ('forecast', 'Forecast')
        ]
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.insight_type} - {self.created_at.strftime('%Y-%m-%d')}"
    
    class Meta:
        ordering = ['-created_at']
