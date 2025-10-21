# finance/forms.py
"""
Django forms for FinSIGHT.
"""

from django import forms
from .models import Transaction, UserProfile, RecurringPayment, Category


class TransactionForm(forms.ModelForm):
    """Form for adding/editing transactions"""
    
    class Meta:
        model = Transaction
        fields = ['description', 'amount', 'date', 'category', 'notes']
        widgets = {
            'description': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter description'
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01'
            }),
            'date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'category': forms.Select(attrs={
                'class': 'form-control'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Optional notes'
            }),
        }


class UserProfileForm(forms.ModelForm):
    """Form for user profile settings"""
    
    class Meta:
        model = UserProfile
        fields = ['monthly_savings_goal', 'financial_goal_description']
        widgets = {
            'monthly_savings_goal': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '500.00',
                'step': '0.01'
            }),
            'financial_goal_description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'E.g., Save for a vacation, build emergency fund...'
            }),
        }
        labels = {
            'monthly_savings_goal': 'Monthly Savings Goal ($)',
            'financial_goal_description': 'What are you saving for?'
        }


class RecurringPaymentForm(forms.ModelForm):
    """Form for manually adding recurring payments"""
    
    class Meta:
        model = RecurringPayment
        fields = ['name', 'amount', 'category', 'frequency', 'due_day', 'start_date']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'E.g., Netflix Subscription'
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01'
            }),
            'category': forms.Select(attrs={
                'class': 'form-control'
            }),
            'frequency': forms.Select(attrs={
                'class': 'form-control'
            }),
            'due_day': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '31',
                'placeholder': 'Day of month (1-31) or day of week (0-6)'
            }),
            'start_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
        }
        help_texts = {
            'due_day': 'For monthly: day of month (1-31). For weekly: day of week (0=Monday, 6=Sunday)',
            'start_date': 'When did this recurring payment start?'
        }