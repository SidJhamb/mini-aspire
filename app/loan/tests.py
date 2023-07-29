from datetime import date
from django.test import TestCase
from django.urls import reverse
from core.models import (
    Loan,
    User,
    Repayment,
    LoanStatus,
    RepaymentStatus
)
from rest_framework.test import APIClient
from rest_framework import status


class UserAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_create_user(self):
        response = self.client.post(reverse('api:user'), data={"user_name": "sample_user"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.filter(user_name="sample_user").count(), 1)
        self.assertEqual(response.data["user_name"], 'sample_user')

        response = self.client.post(reverse('api:user'), data={"user_name": "sample_user"})
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_create_bad_request(self):
        response = self.client.post(reverse('api:user'), data={})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class LoanAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user_1 = User.objects.create(user_name='sample_user_1')
        self.user_2 = User.objects.create(user_name='sample_user_2')
        self.loan_1 = Loan.objects.create(amount=100, terms=2, user=self.user_1)
        Repayment.objects.create(loan=self.loan_1, amount=50, due_date=date(2023, 7, 31))
        Repayment.objects.create(loan=self.loan_1, amount=50, due_date=date(2023, 8, 6))

        self.loan_2 = Loan.objects.create(amount=100, terms=2, user=self.user_2)
        Repayment.objects.create(loan=self.loan_2, amount=50, due_date=date(2023, 7, 31))
        Repayment.objects.create(loan=self.loan_2, amount=50, due_date=date(2023, 8, 6))

        self.request_header_1 = {'HTTP_USERNAME': 'sample_user_1'}
        self.request_header_2 = {'HTTP_USERNAME': 'sample_user_2'}

    def test_get_loans_unauthorized(self):
        response = self.client.get(reverse('api:loan'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        invalid_request_header = {'HTTP_USERNAME': 'sample_user_4'}
        response = self.client.get(reverse('api:loan'), **invalid_request_header)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_loans_for_user(self):
        response = self.client.get(reverse('api:loan'), **self.request_header_1)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['amount'], 100)
        self.assertEqual(response.data[0]['terms'], 2)
        self.assertEqual(response.data[0]['status'], 'PENDING')
        self.assertEqual(len(response.data[0]['repayments']), 2)

        response = self.client.get(reverse('api:loan'), **self.request_header_2)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['amount'], 100)
        self.assertEqual(response.data[0]['terms'], 2)
        self.assertEqual(response.data[0]['status'], 'PENDING')
        self.assertEqual(len(response.data[0]['repayments']), 2)

    def test_create_loan(self):
        request_data = {
            "amount": 3000,
            "terms": 3,
        }
        response = self.client.post(reverse('api:loan'), data=request_data, **self.request_header_1)
        loan = Loan.objects.get(id=response.data['id'])
        self.assertEqual(loan.amount, 3000)
        self.assertEqual(loan.terms, 3)
        self.assertEqual(loan.status, LoanStatus.PENDING)
        self.assertEqual(Loan.objects.filter(id=response.data['id']).count(), 1)

        repayment = Repayment.objects.filter(loan_id=response.data['id']).first()
        self.assertEqual(repayment.amount, request_data['amount']/request_data['terms'])
        self.assertEqual(repayment.status, LoanStatus.PENDING)
        self.assertEqual(Repayment.objects.filter(loan_id=response.data['id']).count(), request_data['terms'])

    def test_create_loan_bad_request(self):
        response = self.client.post(reverse('api:loan'), data={"amount": 3000, "number_of_terms": 3}, **self.request_header_1)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_loan_unauthorized(self):
        response = self.client.post(reverse('api:loan'), data={"amount": 3000, "terms": 3})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_approve_loan(self):
        self.assertEqual(self.loan_1.status, LoanStatus.PENDING)
        response = self.client.put('/approval/{}'.format(str(self.loan_1.id)))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.loan_1.refresh_from_db()
        self.assertEqual(self.loan_1.status, LoanStatus.APPROVED)

    def test_approve_missing_loan(self):
        response = self.client.put('/approval/5')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class RepaymentAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create(user_name='sample_user')
        self.request_header = {'HTTP_USERNAME': 'sample_user'}

    def test_repay_loan_unauthorized(self):
        response = self.client.put('/repayment/1/1', data={'amount': 1500})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_repay_loan(self):
        # Create the Loan
        response = self.client.post(reverse('api:loan'), data={"amount": 3000, "terms": 2}, **self.request_header)
        loan_id = response.data['id']
        loan = Loan.objects.get(id=loan_id)
        self.assertEqual(loan.status, LoanStatus.PENDING)

        # Approve the Loan
        response = self.client.put('/approval/{}'.format(str(loan.id)))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        loan.refresh_from_db()
        self.assertEqual(loan.status, LoanStatus.APPROVED)

        repayment_ids = []
        repayments = Repayment.objects.filter(loan_id=loan_id).all()
        for repayment in repayments:
            repayment_ids.append(repayment.id)

        # Make first repayment
        self.assertEqual(repayments[0].status, RepaymentStatus.PENDING)
        response = self.client.put('/repayment/{}/{}'.format(loan_id, repayment_ids[0]),
                                   data={'amount': 1500}, **self.request_header)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        repayments[0].refresh_from_db()
        self.assertEqual(repayments[0].status, RepaymentStatus.PAID)

        # Make second repayment
        self.assertEqual(repayments[1].status, RepaymentStatus.PENDING)
        response = self.client.put('/repayment/{}/{}'.format(loan_id, repayment_ids[1]),
                                   data={'amount': 1500}, **self.request_header)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        repayments[1].refresh_from_db()
        self.assertEqual(repayments[1].status, RepaymentStatus.PAID)

        # Assert that the loan is marked as PAID
        loan.refresh_from_db()
        self.assertEqual(loan.status, LoanStatus.PAID)

    def test_repay_loan_with_rebalance(self):
        # Create the Loan
        response = self.client.post(reverse('api:loan'), data={"amount": 300, "terms": 3}, **self.request_header)
        loan_id = response.data['id']
        loan = Loan.objects.get(id=loan_id)
        self.assertEqual(loan.status, LoanStatus.PENDING)

        # Approve the Loan
        response = self.client.put('/approval/{}'.format(str(loan.id)))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        loan.refresh_from_db()
        self.assertEqual(loan.status, LoanStatus.APPROVED)

        repayment_ids = []
        repayments = Repayment.objects.filter(loan_id=loan_id).all()
        for repayment in repayments:
            repayment_ids.append(repayment.id)

        # Make first repayment with extra amount
        self.assertEqual(repayments[0].status, RepaymentStatus.PENDING)
        response = self.client.put('/repayment/{}/{}'.format(loan_id, repayment_ids[0]),
                                   data={'amount': 120}, **self.request_header)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        repayments[0].refresh_from_db()
        self.assertEqual(repayments[0].status, RepaymentStatus.PAID)

        # Assert the unpaid repayments are rebalanced with the updated due amount
        repayments[1].refresh_from_db()
        repayments[2].refresh_from_db()
        self.assertEqual(repayments[1].amount, 90)
        self.assertEqual(repayments[2].amount, 90)

        # Make second repayment with extra amount
        self.assertEqual(repayments[1].status, RepaymentStatus.PENDING)
        response = self.client.put('/repayment/{}/{}'.format(loan_id, repayment_ids[1]),
                                   data={'amount': 100}, **self.request_header)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        repayments[1].refresh_from_db()
        self.assertEqual(repayments[1].status, RepaymentStatus.PAID)

        # Assert the unpaid repayment is rebalanced with the updated due amount
        repayments[2].refresh_from_db()
        self.assertEqual(repayments[2].amount, 80)

        # Make third repayment with the required amount
        self.assertEqual(repayments[2].status, RepaymentStatus.PENDING)
        response = self.client.put('/repayment/{}/{}'.format(loan_id, repayment_ids[2]),
                                   data={'amount': 80}, **self.request_header)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        repayments[2].refresh_from_db()
        self.assertEqual(repayments[2].status, RepaymentStatus.PAID)

        # Assert that the loan is marked as PAID
        loan.refresh_from_db()
        self.assertEqual(loan.status, LoanStatus.PAID)

    def test_repay_loan_insufficient_amount_error(self):
        # Create the Loan
        response = self.client.post(reverse('api:loan'), data={"amount": 3000, "terms": 2}, **self.request_header)
        loan_id = response.data['id']

        loan = Loan.objects.get(id=loan_id)
        self.assertEqual(loan.status, LoanStatus.PENDING)

        # Approve the Loan
        response = self.client.put('/approval/{}'.format(str(loan.id)))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        loan.refresh_from_db()
        self.assertEqual(loan.status, LoanStatus.APPROVED)

        repayment_ids = []
        repayments = Repayment.objects.filter(loan_id=loan_id).all()
        for repayment in repayments:
            repayment_ids.append(repayment.id)

        # Make first repayment with less than expected amount, and check that it fails.
        self.assertEqual(repayments[0].status, RepaymentStatus.PENDING)
        response = self.client.put('/repayment/{}/{}'.format(loan_id, repayment_ids[0]),
                                   data={'amount': 1000}, **self.request_header)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_repay_loan_unapproved_error(self):
        # Create the Loan
        response = self.client.post(reverse('api:loan'), data={"amount": 3000, "terms": 2}, **self.request_header)
        loan_id = response.data['id']

        loan = Loan.objects.get(id=loan_id)
        self.assertEqual(loan.status, LoanStatus.PENDING)

        repayment_ids = []
        repayments = Repayment.objects.filter(loan_id=loan_id).all()
        for repayment in repayments:
            repayment_ids.append(repayment.id)

        # Make first repayment for the loan that has not been approved yet, and check that it fails.
        self.assertEqual(repayments[0].status, RepaymentStatus.PENDING)
        response = self.client.put('/repayment/{}/{}'.format(loan_id, repayment_ids[0]),
                                   data={'amount': 1000}, **self.request_header)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)





