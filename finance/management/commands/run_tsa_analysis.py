# finance/management/commands/run_tsa_analysis.py
"""
Management command to run time series analysis for all users.
Usage: python manage.py run_tsa_analysis --username=testuser
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

from finance.services.time_series_analyzer import TimeSeriesAnalyzer


class Command(BaseCommand):
    help = 'Run time series analysis to detect recurring patterns'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, help='Specific user to analyze')
        parser.add_argument('--all', action='store_true', help='Analyze all users')

    def handle(self, *args, **kwargs):
        username = kwargs.get('username')
        analyze_all = kwargs.get('all')
        
        if username:
            users = [User.objects.get(username=username)]
        elif analyze_all:
            users = User.objects.all()
        else:
            self.stdout.write(self.style.ERROR('Please specify --username or --all'))
            return
        
        for user in users:
            self.stdout.write(f'\nAnalyzing user: {user.username}')
            self.stdout.write('-' * 50)
            
            analyzer = TimeSeriesAnalyzer(user)
            analyzer.load_data()
            
            if analyzer.df is None or len(analyzer.df) == 0:
                self.stdout.write(self.style.WARNING('No transactions found'))
                continue
            
            # Analyze seasonality
            self.stdout.write('\n1. Seasonality Analysis:')
            seasonality = analyzer.analyze_seasonality()
            
            if 'error' not in seasonality:
                self.stdout.write(f'   Mean daily spending: ${seasonality["mean"]:.2f}')
                self.stdout.write(f'   Std deviation: ${seasonality["std"]:.2f}')
                
                if seasonality.get('has_strong_seasonality'):
                    strength = seasonality.get('seasonality_strength', 0)
                    self.stdout.write(self.style.SUCCESS(
                        f'   Strong seasonality detected (strength: {strength:.2%})'
                    ))
            
            # Detect recurring patterns
            self.stdout.write('\n2. Recurring Pattern Detection:')
            patterns = analyzer.detect_recurring_patterns()
            
            if patterns:
                self.stdout.write(self.style.SUCCESS(f'   Found {len(patterns)} potential recurring payments:'))
                for pattern in patterns:
                    self.stdout.write(
                        f'   • {pattern["description"]}: ${pattern["amount"]:.2f} '
                        f'({pattern["frequency"]}) - {pattern["confidence"]:.1%} confidence'
                    )
            else:
                self.stdout.write('   No recurring patterns detected')
            
            # Detect anomalies
            self.stdout.write('\n3. Anomaly Detection:')
            anomalies = analyzer.detect_anomalies()
            
            if anomalies:
                self.stdout.write(self.style.WARNING(f'   Found {len(anomalies)} unusual spending days:'))
                for anomaly in anomalies[:5]:  # Show top 5
                    self.stdout.write(
                        f'   • {anomaly["date"]}: ${anomaly["amount"]:.2f} '
                        f'(avg: ${anomaly["mean"]:.2f}, z-score: {anomaly["z_score"]:.1f})'
                    )
            else:
                self.stdout.write(self.style.SUCCESS('   No anomalies detected'))
            
            # Calculate threshold
            threshold_info = analyzer.calculate_spending_threshold()
            self.stdout.write('\n4. Spending Threshold:')
            self.stdout.write(f'   Average daily discretionary: ${threshold_info["avg_daily_spending"]:.2f}')
            self.stdout.write(f'   Unusual spending threshold: ${threshold_info["threshold"]:.2f}')
            
            self.stdout.write('\n' + '=' * 50)
        
        self.stdout.write(self.style.SUCCESS('\nAnalysis complete!'))