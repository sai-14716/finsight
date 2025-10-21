# finance/tests.py
"""
Unit tests for FinSIGHT.
"""

from django.test import TestCase
from django.contrib.auth.models import User
from datetime import datetime, timedelta

from .models import Transaction, Category, UserProfile, RecurringPayment
from .services.time_series_analyzer import TimeSeriesAnalyzer, ForecastEngine


class TimeSeriesAnalyzerTests(TestCase):
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        UserProfile.objects.create(user=self.user, monthly_savings_goal=500)
        
        # Create categories
        self.food_category = Category.objects.create(name='Food', icon='🍔')
        self.transport_category = Category.objects.create(name='Transport', icon='🚗')
        
        # Create recurring transactions (monthly)
        base_date = datetime.now().date()
        for i in range(6):
            date = base_date - timedelta(days=30*i)
            Transaction.objects.create(
                user=self.user,
                description='Netflix',
                amount=15.99,
                date=date,
                category=self.food_category
            )
        
        # Create random discretionary transactions
        for i in range(90):
            date = base_date - timedelta(days=i)
            Transaction.objects.create(
                user=self.user,
                description='Random Store',
                amount=25.50,
                date=date,
                category=self.transport_category
            )
    
    def test_load_data(self):
        """Test data loading"""
        analyzer = TimeSeriesAnalyzer(self.user)
        df = analyzer.load_data()
        
        self.assertIsNotNone(df)
        self.assertGreater(len(df), 0)
    
    def test_detect_recurring_patterns(self):
        """Test recurring pattern detection"""
        analyzer = TimeSeriesAnalyzer(self.user)
        analyzer.load_data()
        
        patterns = analyzer.detect_recurring_patterns(min_occurrences=3)
        
        self.assertGreater(len(patterns), 0)
        
        # Check if Netflix was detected
        netflix_pattern = next((p for p in patterns if 'Netflix' in p['description']), None)
        self.assertIsNotNone(netflix_pattern)
        self.assertEqual(netflix_pattern['frequency'], 'monthly')
    
    def test_anomaly_detection(self):
        """Test anomaly detection"""
        # Add an anomaly
        Transaction.objects.create(
            user=self.user,
            description='Expensive Purchase',
            amount=500.00,
            date=datetime.now().date(),
            category=self.food_category
        )
        
        analyzer = TimeSeriesAnalyzer(self.user)
        analyzer.load_data()
        
        anomalies = analyzer.detect_anomalies(n_std=2.0)
        
        self.assertGreater(len(anomalies), 0)
    
    def test_calculate_threshold(self):
        """Test spending threshold calculation"""
        analyzer = TimeSeriesAnalyzer(self.user)
        analyzer.load_data()
        
        threshold_info = analyzer.calculate_spending_threshold()
        
        self.assertIn('avg_daily_spending', threshold_info)
        self.assertIn('threshold', threshold_info)
        self.assertGreater(threshold_info['avg_daily_spending'], 0)


class ForecastEngineTests(TestCase):
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(username='testuser2', password='testpass123')
        UserProfile.objects.create(user=self.user)
        
        # Create recurring payment
        self.category = Category.objects.create(name='Bills', icon='💡')
        RecurringPayment.objects.create(
            user=self.user,
            name='Rent',
            amount=1200.00,
            category=self.category,
            frequency='monthly',
            due_day=1,
            start_date=datetime.now().date() - timedelta(days=365),
            confirmed_by_user=True
        )
    
    def test_forecast_next_month(self):
        """Test monthly forecast generation"""
        engine = ForecastEngine(self.user)
        forecast = engine.forecast_next_month()
        
        self.assertIn('deterministic_spend', forecast)
        self.assertIn('projected_discretionary', forecast)
        self.assertIn('total_forecast', forecast)
        self.assertIn('payment_schedule', forecast)
        
        # Check if rent is in the schedule
        self.assertGreater(len(forecast['payment_schedule']), 0)


class ModelsTests(TestCase):
    
    def test_user_profile_creation(self):
        """Test UserProfile model"""
        user = User.objects.create_user(username='testuser3', password='testpass123')
        profile = UserProfile.objects.create(
            user=user,
            monthly_savings_goal=750.00,
            financial_goal_description='Save for vacation'
        )
        
        self.assertEqual(profile.user, user)
        self.assertEqual(profile.monthly_savings_goal, 750.00)
    
    def test_transaction_creation(self):
        """Test Transaction model"""
        user = User.objects.create_user(username='testuser4', password='testpass123')
        category = Category.objects.create(name='Shopping', icon='🛍️')
        
        transaction = Transaction.objects.create(
            user=user,
            description='Amazon Purchase',
            amount=89.99,
            date=datetime.now().date(),
            category=category
        )
        
        self.assertEqual(transaction.user, user)
        self.assertEqual(transaction.category, category)
        self.assertEqual(transaction.amount, 89.99)
        self.assertFalse(transaction.is_recurring)
    
    def test_recurring_payment_creation(self):
        """Test RecurringPayment model"""
        user = User.objects.create_user(username='testuser5', password='testpass123')
        category = Category.objects.create(name='Subscriptions', icon='📱')
        
        payment = RecurringPayment.objects.create(
            user=user,
            name='Netflix',
            amount=15.99,
            category=category,
            frequency='monthly',
            due_day=15,
            start_date=datetime.now().date(),
            confirmed_by_user=True
        )
        
        self.assertEqual(payment.user, user)
        self.assertEqual(payment.frequency, 'monthly')
        self.assertTrue(payment.is_active)