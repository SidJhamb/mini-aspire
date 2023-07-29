"""
URL mappings for the loan APIs.
"""
from django.urls import path
from .views import loan_approval

from loan import views

app_name = 'api'

urlpatterns = [
    path('user', views.UserView.as_view(), name='user'),
    path('loan', views.LoanView.as_view(), name='loan'),
    path('approval/<int:loan_id>', loan_approval),
    path('repayment/<int:loan_id>/<int:repayment_id>',  views.RepaymentView.as_view(), name='repayment'),
]
