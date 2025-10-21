# finance/admin.py
"""
Django admin configuration for FinSIGHT models.
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import (
    UserProfile, Category, Transaction, RecurringPayment,
    PendingRecurringConfirmation, FinancialInsight
)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'monthly_savings_goal', 'last_sync_date', 'created_at']
    list_filter = ['created_at', 'last_sync_date']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Financial Goals', {
            'fields': ('monthly_savings_goal', 'financial_goal_description')
        }),
        ('Plaid Integration', {
            'fields': ('plaid_access_token', 'last_sync_date')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'icon', 'plaid_category', 'transaction_count']
    search_fields = ['name', 'plaid_category']
    list_filter = ['created_at']
    
    def transaction_count(self, obj):
        count = obj.transactions.count()
        return format_html('<strong>{}</strong>', count)
    transaction_count.short_description = 'Transactions'


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['date', 'user', 'description', 'amount_display', 'category', 'is_recurring', 'is_anomaly']
    list_filter = ['date', 'is_recurring', 'is_anomaly', 'category', 'created_at']
    search_fields = ['description', 'user__username']
    date_hierarchy = 'date'
    readonly_fields = ['created_at', 'updated_at', 'plaid_transaction_id']
    
    fieldsets = (
        ('Transaction Details', {
            'fields': ('user', 'description', 'amount', 'date', 'category')
        }),
        ('Classification', {
            'fields': ('is_recurring', 'recurring_frequency', 'is_anomaly', 'anomaly_score')
        }),
        ('Plaid Data', {
            'fields': ('plaid_transaction_id',),
            'classes': ('collapse',)
        }),
        ('Additional Info', {
            'fields': ('notes', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def amount_display(self, obj):
        color = 'green' if obj.amount > 0 else 'red'
        return format_html('<span style="color: {};">${:.2f}</span>', color, obj.amount)
    amount_display.short_description = 'Amount'
    
    actions = ['mark_as_recurring', 'mark_as_not_recurring', 'mark_as_anomaly']
    
    def mark_as_recurring(self, request, queryset):
        queryset.update(is_recurring=True)
        self.message_user(request, f'{queryset.count()} transactions marked as recurring.')
    mark_as_recurring.short_description = 'Mark as recurring'
    
    def mark_as_not_recurring(self, request, queryset):
        queryset.update(is_recurring=False)
        self.message_user(request, f'{queryset.count()} transactions marked as not recurring.')
    mark_as_not_recurring.short_description = 'Mark as not recurring'
    
    def mark_as_anomaly(self, request, queryset):
        queryset.update(is_anomaly=True)
        self.message_user(request, f'{queryset.count()} transactions marked as anomalies.')
    mark_as_anomaly.short_description = 'Mark as anomaly'


@admin.register(RecurringPayment)
class RecurringPaymentAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'amount_display', 'frequency', 'due_day', 'is_active', 'confirmed_by_user']
    list_filter = ['frequency', 'is_active', 'confirmed_by_user', 'auto_detected']
    search_fields = ['name', 'user__username']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Payment Information', {
            'fields': ('user', 'name', 'amount', 'category')
        }),
        ('Schedule', {
            'fields': ('frequency', 'due_day', 'start_date', 'end_date')
        }),
        ('Status', {
            'fields': ('is_active', 'auto_detected', 'confirmed_by_user')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def amount_display(self, obj):
        return format_html('<strong>${:.2f}</strong>', obj.amount)
    amount_display.short_description = 'Amount'


@admin.register(PendingRecurringConfirmation)
class PendingRecurringConfirmationAdmin(admin.ModelAdmin):
    list_display = ['description', 'user', 'amount', 'frequency', 'confidence_display', 'created_at']
    list_filter = ['frequency', 'created_at']
    search_fields = ['description', 'user__username']
    filter_horizontal = ['related_transactions']
    
    def confidence_display(self, obj):
        percentage = obj.confidence_score * 100
        color = 'green' if percentage >= 80 else 'orange' if percentage >= 60 else 'red'
        return format_html('<span style="color: {};">{:.1f}%</span>', color, percentage)
    confidence_display.short_description = 'Confidence'


@admin.register(FinancialInsight)
class FinancialInsightAdmin(admin.ModelAdmin):
    list_display = ['user', 'insight_type', 'created_at', 'is_read', 'preview']
    list_filter = ['insight_type', 'is_read', 'created_at']
    search_fields = ['user__username', 'insight_text']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    
    def preview(self, obj):
        return obj.insight_text[:100] + '...' if len(obj.insight_text) > 100 else obj.insight_text
    preview.short_description = 'Preview'


# Customize admin site
admin.site.site_header = 'FinSIGHT Administration'
admin.site.site_title = 'FinSIGHT Admin'
admin.site.index_title = 'Finance Management Dashboard'
