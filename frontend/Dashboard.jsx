import React, { useState, useEffect } from 'react';
import { LineChart, Line, BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { RefreshCw, TrendingUp, TrendingDown, DollarSign, Calendar, AlertCircle, CheckCircle, X } from 'lucide-react';

const COLORS = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899', '#06B6D4', '#84CC16'];

const FinSIGHTDashboard = () => {
  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [generatingInsight, setGeneratingInsight] = useState(false);
  const [activeTab, setActiveTab] = useState('overview');

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    setLoading(true);
    // Simulated data - replace with actual API call
    setTimeout(() => {
      setDashboardData({
        profile: {
          savings_goal: 500,
          goal_description: 'Save for vacation',
          last_sync: '2025-10-20T14:30:00'
        },
        spending: {
          total_last_30_days: 2450.75,
          by_category: {
            'Food & Drink': 650.50,
            'Transportation': 320.00,
            'Shopping': 480.25,
            'Entertainment': 200.00,
            'Bills & Utilities': 600.00,
            'Healthcare': 200.00
          }
        },
        forecast: {
          total_forecast: 2580.00,
          deterministic_spend: 1200.00,
          projected_discretionary: 1380.00,
          avg_daily_discretionary: 46.00,
          payment_schedule: [
            { date: '2025-10-25', name: 'Netflix', amount: 15.99, category: 'Entertainment' },
            { date: '2025-10-28', name: 'Gym Membership', amount: 50.00, category: 'Fitness' },
            { date: '2025-11-01', name: 'Rent', amount: 1200.00, category: 'Housing' }
          ]
        },
        anomalies: {
          count: 2,
          threshold: { avg_daily_spending: 46.00, threshold: 120.00, std: 37.00 },
          recent: [
            { date: '2025-10-15', amount: 185.50, mean: 46.00, z_score: 3.2 },
            { date: '2025-10-18', amount: 152.00, mean: 46.00, z_score: 2.5 }
          ]
        },
        recent_transactions: [
          { id: 1, description: 'Whole Foods', amount: 125.50, date: '2025-10-20', category: 'Food & Drink', is_anomaly: false },
          { id: 2, description: 'Uber', amount: 25.00, date: '2025-10-20', category: 'Transportation', is_anomaly: false },
          { id: 3, description: 'Amazon', amount: 89.99, date: '2025-10-19', category: 'Shopping', is_anomaly: false }
        ],
        pending_confirmations: [
          { id: 1, description: 'Spotify', amount: 9.99, frequency: 'monthly', confidence: 0.95 }
        ],
        latest_insight: {
          text: "Great progress! Your spending last month was $2,450.75, which is within range of your $500 monthly savings goal. We noticed your Food & Drink spending was your largest category at $650.50. Consider setting a weekly budget of $150 for this category to help you save even more. Your forecast for next month looks stable at $2,580, with your rent payment coming up on November 1st.",
          type: 'monthly_summary',
          created_at: '2025-10-20T10:00:00'
        }
      });
      setLoading(false);
    }, 800);
  };

  const syncTransactions = async () => {
    setSyncing(true);
    setTimeout(() => {
      setSyncing(false);
      fetchDashboardData();
    }, 2000);
  };

  const generateInsights = async () => {
    setGeneratingInsight(true);
    setTimeout(() => {
      setGeneratingInsight(false);
      fetchDashboardData();
    }, 3000);
  };

  const confirmRecurring = async (id, action) => {
    console.log(`${action} recurring payment ${id}`);
    fetchDashboardData();
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-b-4 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600 font-medium">Loading your financial insights...</p>
        </div>
      </div>
    );
  }

  const categoryData = Object.entries(dashboardData.spending.by_category).map(([name, value]) => ({
    name,
    value: parseFloat(value)
  }));

  const monthlyData = [
    { month: 'May', amount: 2200 },
    { month: 'Jun', amount: 2400 },
    { month: 'Jul', amount: 2150 },
    { month: 'Aug', amount: 2600 },
    { month: 'Sep', amount: 2300 },
    { month: 'Oct', amount: dashboardData.spending.total_last_30_days }
  ];

  const isOverBudget = dashboardData.spending.total_last_30_days > dashboardData.profile.savings_goal + 2000;

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50">
      {/* Header */}
      <header className="bg-white shadow-md">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">FinSIGHT</h1>
              <p className="text-sm text-gray-600 mt-1">Smart Personal Finance Management</p>
            </div>
            <button
              onClick={syncTransactions}
              disabled={syncing}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-5 h-5 ${syncing ? 'animate-spin' : ''}`} />
              {syncing ? 'Syncing...' : 'Sync Transactions'}
            </button>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Tabs */}
        <div className="flex gap-2 mb-6 border-b border-gray-200">
          {['overview', 'analytics', 'recurring', 'forecast'].map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-6 py-3 font-medium capitalize transition-colors ${
                activeTab === tab
                  ? 'text-blue-600 border-b-2 border-blue-600'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              {tab}
            </button>
          ))}
        </div>

        {/* AI Insight Card */}
        {dashboardData.latest_insight && (
          <div className="bg-gradient-to-r from-blue-500 to-indigo-600 rounded-2xl p-6 mb-6 text-white shadow-lg">
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-2">
                <TrendingUp className="w-6 h-6" />
                <h2 className="text-xl font-bold">AI Financial Insight</h2>
              </div>
              <button
                onClick={generateInsights}
                disabled={generatingInsight}
                className="px-4 py-2 bg-white/20 backdrop-blur-sm rounded-lg hover:bg-white/30 transition-colors text-sm disabled:opacity-50"
              >
                {generatingInsight ? 'Generating...' : 'Refresh Insight'}
              </button>
            </div>
            <p className="text-lg leading-relaxed">{dashboardData.latest_insight.text}</p>
          </div>
        )}

        {activeTab === 'overview' && (
          <>
            {/* Key Metrics */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
              <div className="bg-white rounded-xl p-6 shadow-md">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-medium text-gray-600">Last 30 Days</h3>
                  <DollarSign className="w-5 h-5 text-blue-600" />
                </div>
                <p className="text-3xl font-bold text-gray-900">
                  ${dashboardData.spending.total_last_30_days.toFixed(2)}
                </p>
                <p className="text-sm text-gray-500 mt-1">Total spending</p>
              </div>

              <div className="bg-white rounded-xl p-6 shadow-md">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-medium text-gray-600">Next Month Forecast</h3>
                  <Calendar className="w-5 h-5 text-purple-600" />
                </div>
                <p className="text-3xl font-bold text-gray-900">
                  ${dashboardData.forecast.total_forecast.toFixed(2)}
                </p>
                <p className="text-sm text-gray-500 mt-1">Projected spending</p>
              </div>

              <div className="bg-white rounded-xl p-6 shadow-md">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-medium text-gray-600">Savings Goal</h3>
                  {isOverBudget ? (
                    <TrendingDown className="w-5 h-5 text-red-600" />
                  ) : (
                    <TrendingUp className="w-5 h-5 text-green-600" />
                  )}
                </div>
                <p className="text-3xl font-bold text-gray-900">
                  ${dashboardData.profile.savings_goal.toFixed(2)}
                </p>
                <p className="text-sm text-gray-500 mt-1">{dashboardData.profile.goal_description}</p>
              </div>
            </div>

            {/* Anomalies Alert */}
            {dashboardData.anomalies.count > 0 && (
              <div className="bg-amber-50 border-l-4 border-amber-500 rounded-lg p-4 mb-6">
                <div className="flex items-start gap-3">
                  <AlertCircle className="w-5 h-5 text-amber-600 mt-0.5" />
                  <div>
                    <h3 className="font-semibold text-amber-900">Unusual Spending Detected</h3>
                    <p className="text-sm text-amber-800 mt-1">
                      We found {dashboardData.anomalies.count} day(s) with spending above your typical range of $
                      {dashboardData.anomalies.threshold.threshold.toFixed(2)}.
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Pending Confirmations */}
            {dashboardData.pending_confirmations.length > 0 && (
              <div className="bg-white rounded-xl p-6 shadow-md mb-6">
                <h3 className="text-lg font-bold text-gray-900 mb-4">Confirm Recurring Payments</h3>
                <div className="space-y-3">
                  {dashboardData.pending_confirmations.map(payment => (
                    <div key={payment.id} className="flex items-center justify-between p-4 bg-blue-50 rounded-lg">
                      <div>
                        <p className="font-medium text-gray-900">{payment.description}</p>
                        <p className="text-sm text-gray-600">
                          ${payment.amount} • {payment.frequency} • {(payment.confidence * 100).toFixed(0)}% confidence
                        </p>
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={() => confirmRecurring(payment.id, 'confirm')}
                          className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors flex items-center gap-1"
                        >
                          <CheckCircle className="w-4 h-4" />
                          Yes
                        </button>
                        <button
                          onClick={() => confirmRecurring(payment.id, 'reject')}
                          className="px-4 py-2 bg-gray-300 text-gray-700 rounded-lg hover:bg-gray-400 transition-colors flex items-center gap-1"
                        >
                          <X className="w-4 h-4" />
                          No
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Recent Transactions */}
            <div className="bg-white rounded-xl p-6 shadow-md">
              <h3 className="text-lg font-bold text-gray-900 mb-4">Recent Transactions</h3>
              <div className="space-y-3">
                {dashboardData.recent_transactions.map(txn => (
                  <div key={txn.id} className="flex items-center justify-between p-3 hover:bg-gray-50 rounded-lg transition-colors">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center">
                        <DollarSign className="w-5 h-5 text-blue-600" />
                      </div>
                      <div>
                        <p className="font-medium text-gray-900">{txn.description}</p>
                        <p className="text-sm text-gray-500">{txn.category} • {txn.date}</p>
                      </div>
                    </div>
                    <p className="font-semibold text-gray-900">${txn.amount.toFixed(2)}</p>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}

        {activeTab === 'analytics' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Category Breakdown */}
            <div className="bg-white rounded-xl p-6 shadow-md">
              <h3 className="text-lg font-bold text-gray-900 mb-4">Spending by Category</h3>
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={categoryData}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                    outerRadius={100}
                    fill="#8884d8"
                    dataKey="value"
                  >
                    {categoryData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value) => `$${value.toFixed(2)}`} />
                </PieChart>
              </ResponsiveContainer>
            </div>

            {/* Monthly Trend */}
            <div className="bg-white rounded-xl p-6 shadow-md">
              <h3 className="text-lg font-bold text-gray-900 mb-4">6-Month Spending Trend</h3>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={monthlyData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="month" />
                  <YAxis />
                  <Tooltip formatter={(value) => `$${value.toFixed(2)}`} />
                  <Bar dataKey="amount" fill="#3B82F6" radius={[8, 8, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {activeTab === 'recurring' && (
          <div className="bg-white rounded-xl p-6 shadow-md">
            <h3 className="text-lg font-bold text-gray-900 mb-4">Recurring Payments Schedule</h3>
            <div className="space-y-3">
              {dashboardData.forecast.payment_schedule.map((payment, idx) => (
                <div key={idx} className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 bg-purple-100 rounded-full flex items-center justify-center">
                      <Calendar className="w-6 h-6 text-purple-600" />
                    </div>
                    <div>
                      <p className="font-medium text-gray-900">{payment.name}</p>
                      <p className="text-sm text-gray-500">{payment.category} • Due: {payment.date}</p>
                    </div>
                  </div>
                  <p className="font-semibold text-gray-900">${payment.amount.toFixed(2)}</p>
                </div>
              ))}
            </div>
            <div className="mt-6 pt-6 border-t border-gray-200">
              <div className="flex justify-between items-center">
                <p className="text-lg font-semibold text-gray-900">Total Recurring Payments</p>
                <p className="text-2xl font-bold text-blue-600">
                  ${dashboardData.forecast.deterministic_spend.toFixed(2)}
                </p>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'forecast' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Forecast Summary */}
            <div className="bg-white rounded-xl p-6 shadow-md">
              <h3 className="text-lg font-bold text-gray-900 mb-6">Next 30 Days Forecast</h3>
              <div className="space-y-4">
                <div className="flex justify-between items-center p-4 bg-blue-50 rounded-lg">
                  <div>
                    <p className="text-sm text-gray-600">Recurring Payments</p>
                    <p className="text-sm text-gray-500 mt-1">Fixed monthly expenses</p>
                  </div>
                  <p className="text-2xl font-bold text-blue-600">
                    ${dashboardData.forecast.deterministic_spend.toFixed(2)}
                  </p>
                </div>
                
                <div className="flex justify-between items-center p-4 bg-purple-50 rounded-lg">
                  <div>
                    <p className="text-sm text-gray-600">Projected Discretionary</p>
                    <p className="text-sm text-gray-500 mt-1">Based on ${dashboardData.forecast.avg_daily_discretionary.toFixed(2)}/day avg</p>
                  </div>
                  <p className="text-2xl font-bold text-purple-600">
                    ${dashboardData.forecast.projected_discretionary.toFixed(2)}
                  </p>
                </div>

                <div className="flex justify-between items-center p-4 bg-gradient-to-r from-blue-500 to-purple-600 rounded-lg text-white">
                  <div>
                    <p className="text-sm font-medium">Total Forecast</p>
                    <p className="text-xs opacity-90 mt-1">Estimated total spending</p>
                  </div>
                  <p className="text-3xl font-bold">
                    ${dashboardData.forecast.total_forecast.toFixed(2)}
                  </p>
                </div>
              </div>
            </div>

            {/* Spending Threshold */}
            <div className="bg-white rounded-xl p-6 shadow-md">
              <h3 className="text-lg font-bold text-gray-900 mb-6">Spending Insights</h3>
              <div className="space-y-6">
                <div>
                  <div className="flex justify-between items-center mb-2">
                    <p className="text-sm font-medium text-gray-600">Average Daily Discretionary</p>
                    <p className="text-lg font-bold text-gray-900">
                      ${dashboardData.forecast.avg_daily_discretionary.toFixed(2)}
                    </p>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-3">
                    <div 
                      className="bg-blue-600 h-3 rounded-full transition-all duration-500"
                      style={{ width: '60%' }}
                    ></div>
                  </div>
                </div>

                <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg">
                  <div className="flex items-start gap-3">
                    <AlertCircle className="w-5 h-5 text-amber-600 mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="font-semibold text-amber-900">Unusual Spending Alert</p>
                      <p className="text-sm text-amber-800 mt-1">
                        Daily spending over ${dashboardData.anomalies.threshold.threshold.toFixed(2)} is considered unusual based on your spending patterns.
                      </p>
                    </div>
                  </div>
                </div>

                <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
                  <div className="flex items-start gap-3">
                    <CheckCircle className="w-5 h-5 text-green-600 mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="font-semibold text-green-900">Budget Recommendation</p>
                      <p className="text-sm text-green-800 mt-1">
                        To meet your ${dashboardData.profile.savings_goal.toFixed(2)} savings goal, try to keep daily discretionary spending under ${(dashboardData.forecast.avg_daily_discretionary * 0.9).toFixed(2)}.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Anomalies Detail */}
            {dashboardData.anomalies.recent.length > 0 && (
              <div className="lg:col-span-2 bg-white rounded-xl p-6 shadow-md">
                <h3 className="text-lg font-bold text-gray-900 mb-4">Recent Unusual Spending Days</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {dashboardData.anomalies.recent.map((anomaly, idx) => (
                    <div key={idx} className="p-4 bg-red-50 border border-red-200 rounded-lg">
                      <div className="flex justify-between items-start mb-2">
                        <p className="font-semibold text-gray-900">{anomaly.date}</p>
                        <span className="px-2 py-1 bg-red-200 text-red-800 text-xs font-medium rounded">
                          {anomaly.z_score.toFixed(1)}σ above avg
                        </span>
                      </div>
                      <p className="text-2xl font-bold text-red-600 mb-1">
                        ${anomaly.amount.toFixed(2)}
                      </p>
                      <p className="text-sm text-gray-600">
                        Typical: ${anomaly.mean.toFixed(2)}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 mt-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex justify-between items-center">
            <p className="text-sm text-gray-600">
              Last synced: {new Date(dashboardData.profile.last_sync).toLocaleString()}
            </p>
            <p className="text-sm text-gray-500">
              FinSIGHT © 2025 • Smart Finance Management
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default FinSIGHTDashboard;